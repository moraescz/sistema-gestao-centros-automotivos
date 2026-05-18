from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.utils.decorators import method_decorator
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User, Permission
from django.db.models import Sum, Count, Avg, F, DecimalField, Value
from django.db.models.functions import TruncMonth, Coalesce
from django.http import HttpResponse, JsonResponse
from django.views.generic import TemplateView
import json
from datetime import datetime, timedelta
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from django.db.models import Q, ProtectedError
from django.core.paginator import Paginator
from django.contrib.contenttypes.models import ContentType
from .models import Cliente, Veiculo, Peca, OrdemServico, PecaUtilizada, ConfiguracoesGerais, LogAtividade, ServicoUtilizado, AnexoOrdemServico, Funcionario
from .models import Servico, Agendamento, HorarioFuncionamento, DiaBloqueado, ConfiguracaoSite, FotoTrabalho
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from django.contrib import messages
from .utils import registrar_log, get_primary_color_classes
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.conf import settings
from django.views.decorators.cache import never_cache # <--- Importado
import os
import re
import csv
import pytz
import subprocess
import sys
from django.utils import timezone
from io import BytesIO
from django.db import IntegrityError
from django.urls import reverse
import threading
from django.views.defaults import page_not_found
from .forms import (
    ClienteForm, VeiculoForm, PecaForm, OrdemServicoForm,
    CustomUserCreationForm, CustomUserChangeForm, PecaUtilizadaForm, ConfiguracoesGeraisForm, ServicoUtilizadoForm, AnexoForm
)


# --- 1. MAPA DE MODELOS PADRÃO (CRUD) ---
RELEVANT_MODELS_MAP = {
    'Ordens de Serviço': {'class': OrdemServico, 'template_name': 'OrdemServico'},
    'Clientes':          {'class': Cliente,      'template_name': 'Cliente'},
    'Veículos':          {'class': Veiculo,      'template_name': 'Veiculo'},
    'Peças':             {'class': Peca,         'template_name': 'Peca'},
}

# --- 2. MAPA DE PERMISSÕES CUSTOMIZADAS ---
CUSTOM_PERMS_MAP = {
    'Dashboard': {
        'template_name': 'Dashboard',
        'perm_type': 'view',
        'codename': 'view_dashboard',          # Nome exato no models.py
        'attached_to_model': ConfiguracoesGerais # Modelo onde a permissão foi criada
    },
}
# --- FIM DO MAPA ---

def custom_404_view(request, exception=None):
    """
    Esta view força o Django a renderizar o template 404.html.
    """
    context = {
        'request_path': request.path
    }
    # Renderiza seu template e, crucialmente, define o status HTTP para 404
    return render(request, '404.html', context, status=404)

# --- Função auxiliar para quebrar texto (coloque antes da view ou em utils.py) ---
def wrap_text(canvas_obj, text, x, y, max_width, style=None):
    if style is None:
        style = getSampleStyleSheet()['Normal']
        style.fontSize = 10
        style.textColor = colors.HexColor("#212529")
        
    p = Paragraph(text.replace('\n', '<br/>'), style)
    p.wrapOn(canvas_obj, max_width, 1000) # 1000 é uma altura grande o suficiente
    height = p.height
    p.drawOn(canvas_obj, x, y - height)
    return height


# --- Views de Autenticação ---
# (NÃO PRECISA de @never_cache)
@never_cache  # <--- 3. APLIQUE O DECORATOR AQUI
def login_view(request):
    
    # 4. CARREGUE AS CONFIGURAÇÕES (para o template)
    try:
        configuracoes = ConfiguracoesGerais.carregar()
    except Exception:
        configuracoes = None

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                registrar_log(user, 'LOGIN', f"Utilizador '{user.username}' autenticado.")
                return redirect('home')
        # Se o form for inválido, o 'else' abaixo será executado
    else:
        form = AuthenticationForm()
        
    # 5. PASSE O FORM E AS CONFIGURAÇÕES PARA O TEMPLATE
    context = {
        'form': form,
        'configuracoes': configuracoes
    }
    return render(request, 'cadastros/login.html', context)
    
# (NÃO PRECISA de @never_cache)
def logout_view(request):
    user = request.user
    if user.is_authenticated:
        registrar_log(user, 'LOGOUT', f"Utilizador '{user.username}' terminou a sessão.")
    logout(request)
    return redirect('login')

# --- Página de Acesso Negado ---
# (NÃO PRECISA de @never_cache)
class AcessoNegadoView(TemplateView):
    template_name = 'cadastros/acesso_negado.html'

# --- Dashboard ---
@login_required
@permission_required('cadastros.view_dashboard', login_url='acesso_negado') # Mantendo a permissão do "NOVO"
@never_cache
def home(request):
    """
    View principal do Dashboard, que consolida todas as métricas e
    dados para os gráficos.
    """
    
    # --- Variáveis comuns ---
    ano_atual = datetime.now().year
    meses_pt = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    # --- 1. Métricas dos Cards ---
    total_clientes = Cliente.objects.count()
    total_veiculos = Veiculo.objects.count()
    total_os = OrdemServico.objects.count()
    total_pecas_estoque = Peca.objects.count()
    total_funcionarios = User.objects.filter(is_superuser=False, is_active=True).count()
    # total_os_abertas será calculado na próxima seção
    
    # --- 2. Gráfico de Status da OS (Otimizado) ---
    status_labels_internal = ['AGUARDANDO', 'APROVADO', 'REPROVADO', 'FINALIZADO']
    status_labels_display = ['Aguardando', 'Aprovado', 'Reprovado', 'Finalizado']

    # Query única para agrupar por status e contar
    status_counts = OrdemServico.objects.values('status_aprovacao').annotate(
        count=Count('id')
    ).order_by('status_aprovacao')

    # Converte a query (lista de dicts) num dict para acesso rápido
    status_data_dict = {item['status_aprovacao']: item['count'] for item in status_counts}
    
    # Garante a ordem correta e preenche com 0 se o status não existir
    data_os = [status_data_dict.get(status, 0) for status in status_labels_internal]
    
    # Calcula o total de OS abertas para o card (usando a query otimizada)
    total_os_abertas = status_data_dict.get('AGUARDANDO', 0) + status_data_dict.get('APROVADO', 0)
    total_os_finalizadas = total_os - total_os_abertas 

    # --- 3. Gráficos Financeiros (Faturamento e Ticket Médio) ---
    faturamento_por_mes = {m: 0.0 for m in meses_pt}

    # Query única para os dados financeiros
    # ATENÇÃO: Verifique se os related_names ('pecas_utilizadas', 'servicos_utilizados')
    # e campos ('valor_total') estão corretos conforme seus models.py
    monthly_data_query = OrdemServico.objects.filter(
        finalizada=True,
        data_conclusao__year=ano_atual
    ).annotate(
        mes=TruncMonth('data_conclusao')
    ).values("mes").annotate(
        # Sum pode retornar None se não houver entradas, Coalesce trata isso
        total_pecas=Coalesce(Sum(F('pecas_utilizadas__quantidade_utilizada') * F('pecas_utilizadas__peca__valor_unitario')), Value(0), output_field=DecimalField()),
        total_servicos=Coalesce(Sum('servicos_utilizados__valor'), Value(0), output_field=DecimalField()),
        total_base=Coalesce(Sum('valor_total'), Value(0), output_field=DecimalField()), # Assumindo que valor_total existe na OS
        os_count=Count('id', distinct=True)
    ).annotate(
        # Calcula o faturamento total do mês
        total=F('total_base') + F('total_pecas') + F('total_servicos')
    ).order_by('mes')

    total_faturamento_ano = 0.0
    for item in monthly_data_query:
        if item['mes']:
            mes_nome = meses_pt[item['mes'].month - 1]
            total_mes = float(item['total'])
            os_count = item['os_count']
            
            faturamento_por_mes[mes_nome] = total_mes
            total_faturamento_ano += total_mes

    data_faturamento = list(faturamento_por_mes.values())

    # --- 4. Gráfico: OS Criadas por Mês (Implementado do ANTIGO) ---
    os_criadas_por_mes = {m: 0 for m in meses_pt}
    os_criadas_query = OrdemServico.objects.filter(
        data_abertura__year=ano_atual
    ).annotate(
        mes=TruncMonth('data_abertura')
    ).values('mes').annotate(
        count=Count('id')
    ).order_by('mes')
    
    for item in os_criadas_query:
        if item['mes']:
            mes_nome = meses_pt[item['mes'].month - 1]
            os_criadas_por_mes[mes_nome] = item['count']

    # --- 5. Gráfico: Top 5 Peças Mais Utilizadas (Implementado do ANTIGO) ---
    top_pecas_query = PecaUtilizada.objects.values('peca__nome').annotate(
        total_utilizada=Sum('quantidade_utilizada')
    ).order_by('-total_utilizada')[:5]
    
    # Trata o caso de peças que possam ter sido excluídas (peca__nome=None)
    labels_top_pecas = [item['peca__nome'] if item['peca__nome'] else "Peça Removida" for item in top_pecas_query]
    data_top_pecas = [item['total_utilizada'] for item in top_pecas_query]

    # --- 6. Cálculos Adicionais para Métricas ---
    # Taxa de Conclusão (últimos 30 dias)
    total_os_30_dias = OrdemServico.objects.filter(data_abertura__gte=timezone.now() - timedelta(days=30)).count()
    os_finalizadas_30_dias = OrdemServico.objects.filter(finalizada=True, data_conclusao__gte=timezone.now() - timedelta(days=30)).count()
    taxa_conclusao = (os_finalizadas_30_dias / total_os_30_dias * 100) if total_os_30_dias > 0 else 0

    # Faturamento do Mês Atual
    mes_atual = datetime.now().month
    monthly_data_atual = OrdemServico.objects.filter(
        finalizada=True,
        data_conclusao__year=ano_atual,
        data_conclusao__month=mes_atual
    ).aggregate(
        total_pecas=Coalesce(Sum(F('pecas_utilizadas__quantidade_utilizada') * F('pecas_utilizadas__peca__valor_unitario')), Value(0), output_field=DecimalField()),
        total_servicos=Coalesce(Sum('servicos_utilizados__valor'), Value(0), output_field=DecimalField()),
        total_base=Coalesce(Sum('valor_total'), Value(0), output_field=DecimalField()),
    )
    faturamento_mes_atual = float(monthly_data_atual['total_base'] + monthly_data_atual['total_pecas'] + monthly_data_atual['total_servicos'])

    # Crescimento Mensal
    mes_anterior = mes_atual - 1 if mes_atual > 1 else 12
    ano_anterior = ano_atual if mes_atual > 1 else ano_atual - 1
    monthly_data_anterior = OrdemServico.objects.filter(
        finalizada=True,
        data_conclusao__year=ano_anterior,
        data_conclusao__month=mes_anterior
    ).aggregate(
        total_pecas=Coalesce(Sum(F('pecas_utilizadas__quantidade_utilizada') * F('pecas_utilizadas__peca__valor_unitario')), Value(0), output_field=DecimalField()),
        total_servicos=Coalesce(Sum('servicos_utilizados__valor'), Value(0), output_field=DecimalField()),
        total_base=Coalesce(Sum('valor_total'), Value(0), output_field=DecimalField()),
    )
    faturamento_mes_anterior = float(monthly_data_anterior['total_base'] + monthly_data_anterior['total_pecas'] + monthly_data_anterior['total_servicos'])
    crescimento_mensal = ((faturamento_mes_atual - faturamento_mes_anterior) / faturamento_mes_anterior * 100) if faturamento_mes_anterior > 0 else 0

    # Últimas OS e Logs
    ultimas_os = OrdemServico.objects.select_related('veiculo__cliente').order_by('-data_abertura')[:5]
    ultimos_logs = LogAtividade.objects.select_related('usuario').order_by('-data_hora')[:5]

    # --- 7. Contexto Final (Tudo Junto) ---
    context = {
        # Métricas dos Cards
        'total_clientes': total_clientes,
        'total_veiculos': total_veiculos,
        'total_os': total_os,
        'total_os_abertas': total_os_abertas,
        'total_pecas_estoque': total_pecas_estoque,
        'total_funcionarios': total_funcionarios,

        # Gráfico de Status (4 status)
        'labels_os_json': json.dumps(status_labels_display), # Usando labels amigáveis
        'data_os_json': json.dumps(data_os),

        # Gráficos Financeiros
        'labels_faturamento_json': json.dumps(list(faturamento_por_mes.keys())),
        'data_faturamento_json': json.dumps(data_faturamento),
        'total_faturamento_ano': total_faturamento_ano,
        'faturamento_mes_atual': faturamento_mes_atual,
        'crescimento_mensal': crescimento_mensal,

        # Taxa de Conclusão
        'taxa_conclusao': taxa_conclusao,

        # Gráfico de OS Criadas
        'labels_os_criadas_json': json.dumps(list(os_criadas_por_mes.keys())),
        'data_os_criadas_json': json.dumps(list(os_criadas_por_mes.values())),

        # Gráfico de Top Peças
        'labels_top_pecas_json': json.dumps(labels_top_pecas),
        'data_top_pecas_json': json.dumps(data_top_pecas),

        # Últimas OS e Logs
        'ultimas_os': ultimas_os,
        'ultimos_logs': ultimos_logs,
    }
    
    # Renderizando no template do "NOVO"
    return render(request, 'cadastros/dashboard.html', context)

# --- CRUD de Clientes ---
@login_required
@permission_required('cadastros.view_cliente', login_url='acesso_negado')
@never_cache
def listar_clientes(request):
    print(f"\n--- DEBUG ACESSO CLIENTES ({request.user.username}) ---")
    print(f"Tem 'cadastros.view_cliente'? {request.user.has_perm('cadastros.view_cliente')}")
    print(f"Todas as permissões ativas: {request.user.get_all_permissions()}")
    print("-----------------------------------------------------\n")

    # 3. VERIFICAÇÃO MANUAL (Substitui o decorator para teste)
    if not request.user.has_perm('cadastros.view_cliente'):
        return redirect('acesso_negado') # ou a URL que você definiu
    search_query = request.GET.get('q', '')
    clientes = Cliente.objects.all().order_by('nome').annotate(num_veiculos=Count('veiculos'))

    if search_query:
        clientes = clientes.filter(
            Q(nome__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(telefone__icontains=search_query) |
            Q(cpf__icontains=search_query)
        )

    paginator = Paginator(clientes, 10)
    page_number = request.GET.get('page')
    clientes_page = paginator.get_page(page_number)
    filtros = request.GET

    context = {
        'page_obj': clientes_page,
        'search_query': search_query,
        'filtros': filtros,
    }

    # Se for uma requisição HTMX, renderiza apenas o partial da tabela
    if request.htmx:
        return render(request, 'cadastros/_tabela_clientes.html', context)

    # Caso contrário, renderiza a página completa
    return render(request, 'cadastros/listar_clientes.html', context)

@login_required
@permission_required('cadastros.add_cliente', login_url='/acesso-negado/')
@never_cache
def cadastrar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            novo_cliente = form.save()
            registrar_log(request.user, 'CRIAÇÃO', novo_cliente)
            # MENSAGEM ADICIONADA AQUI
            messages.success(request, 'Cliente cadastrado com sucesso!')
            return redirect('listar_clientes')
    else:
        form = ClienteForm()
    
    return render(request, 'cadastros/cliente_form.html', {'form': form})

def load_cities(request):
    """
    View para carregar cidades dinamicamente com base no estado_id.
    """
    estado_id = request.GET.get('estado_id')
    
    # Filtra as cidades. 
    # Assumindo que seu modelo 'Cidade' tem um campo 'estado' (ForeignKey)
    # e que você quer ordená-las por 'nome'.
    if estado_id:
        cidades = Cidade.objects.filter(estado_id=estado_id).order_by('nome')
    else:
        cidades = Cidade.objects.none()
        
    # Converte o queryset para uma lista de dicionários
    # O JavaScript usará 'id' e 'nome'
    lista_cidades = list(cidades.values('id', 'nome'))
    
    return JsonResponse(lista_cidades, safe=False)

@login_required
@permission_required('cadastros.view_cliente', login_url='/acesso-negado/')
@never_cache
def cliente_detalhe(request, pk):
    """
    Exibe os detalhes de um cliente específico, incluindo a lista de veículos associados.
    """
    cliente = get_object_or_404(Cliente, pk=pk)
    veiculos = cliente.veiculos.all()
    contexto = {
        'cliente': cliente,
        'veiculos': veiculos,
    }
    return render(request, 'cadastros/cliente_detalhe.html', contexto)

@login_required
@permission_required('cadastros.change_cliente', login_url='/acesso-negado/')
@never_cache
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            cliente_editado = form.save()
            registrar_log(request.user, 'ATUALIZAÇÃO', cliente_editado)
            # MENSAGEM ADICIONADA AQUI (usando f-string para personalizar)
            messages.success(request, f'Cliente "{cliente_editado.nome}" atualizado com sucesso!')
            return redirect('listar_clientes')
    else:
        form = ClienteForm(instance=cliente)
    
    return render(request, 'cadastros/editar_cliente.html', {'form': form, 'cliente': cliente})

@login_required
@permission_required('cadastros.delete_cliente', login_url='/acesso-negado/')
@never_cache
def excluir_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    
    if request.method == 'POST':
        # Salva o nome antes de deletar para usar na mensagem
        nome_cliente = cliente.nome 
        registrar_log(request.user, 'EXCLUSÃO', cliente)
        cliente.delete()
        # MENSAGEM ADICIONADA AQUI
        messages.success(request, f'Cliente "{nome_cliente}" excluído com sucesso.')
        return redirect('listar_clientes')
    
    return render(request, 'cadastros/excluir_confirm.html', {'obj': cliente, 'tipo': 'Cliente'})

# --- CRUD de Veículos ---
@login_required
@permission_required('cadastros.view_veiculo', login_url='/acesso-negado/')
@never_cache
def listar_veiculos(request):
    search_query = request.GET.get('q', '')
    veiculos = Veiculo.objects.all().order_by('modelo', 'placa')

    if search_query:
        veiculos = veiculos.filter(
            Q(modelo__icontains=search_query) |
            Q(placa__icontains=search_query) |
            Q(cliente__nome__icontains=search_query) |
            Q(ano__icontains=search_query)
        )

    paginator = Paginator(veiculos, 10)
    page_number = request.GET.get('page')
    veiculos_page = paginator.get_page(page_number)
    
    # NOTA: 'filtros' não é mais necessário se a pesquisa estiver no search_query
    # mas mantemos se você usar em outro lugar.
    filtros = request.GET 

    base_url_params = '&'.join([f'{k}={v}' for k, v in request.GET.items() if k != 'page'])
    context = {
        'page_obj': veiculos_page,
        'search_query': search_query,
        'filtros': filtros,
        'base_url_params': base_url_params
    }

    # --- A CORREÇÃO ESTÁ AQUI ---
    # Nós só precisamos checar se é uma requisição HTMX.
    # Não importa se é da pesquisa ou da paginação.
    if request.htmx:
        return render(request, 'cadastros/_tabela_veiculos.html', context)

    # Caso contrário, renderiza a página completa
    return render(request, 'cadastros/listar_veiculos.html', context)

@login_required
@permission_required('cadastros.add_veiculo', login_url='/acesso-negado/')
@never_cache
def cadastrar_veiculo(request):
    if request.method == 'POST':
        form = VeiculoForm(request.POST)
        if form.is_valid():
            novo_veiculo = form.save()
            registrar_log(request.user, 'CRIAÇÃO', novo_veiculo)
            # MENSAGEM ADICIONADA AQUI
            messages.success(request, 'Veículo cadastrado com sucesso!')
            return redirect('listar_veiculos')
    else:
        form = VeiculoForm()
    
    return render(request, 'cadastros/veiculo_form.html', {'form': form})

@login_required
@permission_required('cadastros.change_veiculo', login_url='/acesso-negado/')
@never_cache
def editar_veiculo(request, pk):
    veiculo = get_object_or_404(Veiculo, pk=pk)
    if request.method == 'POST':
        form = VeiculoForm(request.POST, instance=veiculo)
        if form.is_valid():
            veiculo_editado = form.save()
            registrar_log(request.user, 'ATUALIZAÇÃO', veiculo_editado)
            # MENSAGEM ADICIONADA AQUI (usei a placa como exemplo)
            messages.success(request, f'Veículo placa "{veiculo_editado.placa}" atualizado com sucesso!')
            return redirect('listar_veiculos')
    else:
        form = VeiculoForm(instance=veiculo)
    
    return render(request, 'cadastros/editar_veiculo.html', {'form': form, 'veiculo': veiculo})

@login_required
@permission_required('cadastros.delete_veiculo', login_url='/acesso-negado/')
@never_cache
def excluir_veiculo(request, pk):
    veiculo = get_object_or_404(Veiculo, pk=pk)
    if request.method == 'POST':
        # Salva a placa antes de deletar
        placa_veiculo = veiculo.placa
        # OBS: Você esqueceu o registrar_log aqui, ao contrário da exclusão de cliente
        veiculo.delete()
        # MENSAGEM ADICIONADA AQUI
        messages.success(request, f'Veículo placa "{placa_veiculo}" excluído com sucesso.')
        
        if request.GET.get('from') == 'cliente_detalhe':
            return redirect('cliente_detalhe', pk=veiculo.cliente.pk)
        else:
            return redirect('listar_veiculos')

    return render(request, 'cadastros/excluir_confirm.html', {'obj': veiculo, 'tipo': 'Veículo'})

@login_required
@permission_required('cadastros.view_veiculo', login_url='/acesso-negado/')
@never_cache
def veiculo_historico(request, pk):
    """
    Exibe o histórico completo de um veículo, incluindo todas as ordens de serviço associadas.
    """
    veiculo = get_object_or_404(Veiculo, pk=pk)
    ordens_servico = OrdemServico.objects.filter(veiculo=veiculo).order_by('-data_abertura')
    total_os = ordens_servico.count()
    os_aguardando = ordens_servico.filter(status_aprovacao='AGUARDANDO').count()
    os_aprovadas = ordens_servico.filter(status_aprovacao='APROVADO').count()
    os_reprovadas = ordens_servico.filter(status_aprovacao='REPROVADO').count()
    os_finalizadas = ordens_servico.filter(status_aprovacao='FINALIZADO').count()
    contexto = {
        'veiculo': veiculo,
        'ordens_servico': ordens_servico,
        'total_os': total_os,
        'os_aguardando': os_aguardando,
        'os_aprovadas': os_aprovadas,
        'os_reprovadas': os_reprovadas,
        'os_finalizadas': os_finalizadas,
    }
    return render(request, 'cadastros/veiculo_historico.html', contexto)

# --- CRUD de Peças ---
@login_required
@permission_required('cadastros.view_peca', login_url='/acesso-negado/')
@never_cache
def listar_pecas(request):
    search_query = request.GET.get('q', '')
    pecas = Peca.objects.all().order_by('nome')

    if search_query:
        pecas = pecas.filter(nome__icontains=search_query)

    paginator = Paginator(pecas, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 🔑 Adicione esta lógica para cada peça na página
    for peca in page_obj:
        # Adiciona uma nova propriedade ao objeto Peca usando o estoque mínimo definido na peça
        peca.estoque_baixo = peca.quantidade <= peca.quantidade_minima

    base_url_params = '&'.join([f'{k}={v}' for k, v in request.GET.items() if k != 'page'])
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'base_url_params': base_url_params
    }

    # Se for uma requisição HTMX, renderiza apenas o partial da tabela
    if request.htmx:
        return render(request, 'cadastros/_tabela_pecas.html', context)

    # Caso contrário, renderiza a página completa
    return render(request, 'cadastros/listar_pecas.html', context)

@login_required
@permission_required('cadastros.view_peca', login_url='/acesso-negado/')
@never_cache
def detalhar_peca(request, pk):
    """
    Exibe os detalhes de uma peça específica, incluindo as ordens de serviço 
    onde ela foi utilizada.
    """
    peca = get_object_or_404(Peca, pk=pk)
    
    # Busca as ordens de serviço onde a peça foi utilizada
    # (Esta linha é crucial e faltava no prompt que você colou)
    ordens_servico = OrdemServico.objects.filter(pecas_utilizadas__peca=peca).distinct().order_by('-data_abertura')
    
    contexto = {
        'peca': peca,
        'ordens_servico': ordens_servico,
    }
    return render(request, 'cadastros/peca_detalhe.html', contexto)

def _enviar_alerta_peca_thread(peca_id, user_id):
    """
    Função que roda em segundo plano para enviar o e-mail sem travar a view.
    """
    try:
        # Re-buscamos os objetos do banco para garantir que são "thread-safe"
        peca = Peca.objects.get(pk=peca_id)
        user = User.objects.get(pk=user_id)
        
        print(f"THREAD: Iniciando envio assíncrono para {user.email} sobre '{peca.nome}'...")
        
        # Chama a função do seu modelo que realmente envia o e-mail
        peca.enviar_email_de_alerta_para_usuario(user)
        
        print(f"THREAD: Envio para {user.email} concluído.")
        
    except Exception as e:
        # É CRÍTICO logar o erro aqui, senão a thread falha em silêncio
        print(f"THREAD ERRO: Falha ao enviar email (Peca ID: {peca_id}): {e}")
# -----------------------------------------------------


@login_required
@permission_required('cadastros.add_peca', login_url='/acesso-negado/')
@never_cache
def cadastrar_peca(request):
    if request.method == 'POST':
        form = PecaForm(request.POST, request.FILES)
        if form.is_valid():
            nova_peca = form.save() 
            
            # --- IMPLEMENTAÇÃO ASSÍNCRONA ---
            if getattr(nova_peca, 'deve_enviar_alerta', False):
                print(f"View: Alerta detectado para NOVA PEÇA {nova_peca.nome}. Agendando thread...")
                
                # Inicia a thread para enviar o e-mail em segundo plano
                t = threading.Thread(
                    target=_enviar_alerta_peca_thread,
                    args=[nova_peca.pk, request.user.pk] # Passamos IDs (mais seguro)
                )
                t.start() # A view NÃO espera isso terminar
                
            # --- FIM DA IMPLEMENTAÇÃO ---
            
            log_detalhe = f"Cadastrou a peça: {nova_peca.nome} (ID: {nova_peca.pk})"
            registrar_log(request.user, 'CRIAÇÃO', log_detalhe)
            
            # MENSAGEM ADICIONADA AQUI
            messages.success(request, f'Peça "{nova_peca.nome}" cadastrada com sucesso!')
            
            return redirect('listar_pecas')
    else: 
        form = PecaForm()
    
    return render(request, 'cadastros/peca_form.html', {'form': form, 'titulo': 'Cadastrar Nova Peça', 'is_edit': False})


@login_required
@permission_required('cadastros.change_peca', login_url='/acesso-negado/')
@never_cache
def editar_peca(request, pk):
    peca = get_object_or_404(Peca, pk=pk)
    if request.method == 'POST':
        form = PecaForm(request.POST, request.FILES, instance=peca)
        if form.is_valid():
            peca_editada = form.save() 

            # --- IMPLEMENTAÇÃO ASSÍNCRONA ---
            if getattr(peca_editada, 'deve_enviar_alerta', False):
                print(f"View: Alerta detectado para PEÇA EDITADA {peca_editada.nome}. Agendando thread...")
                
                # Inicia a thread para enviar o e-mail em segundo plano
                t = threading.Thread(
                    target=_enviar_alerta_peca_thread,
                    args=[peca_editada.pk, request.user.pk] # Passamos IDs
                )
                t.start() # A view NÃO espera isso terminar
                
            # --- FIM DA IMPLEMENTAÇÃO ---
            
            log_detalhe = f"Editou a peça: {peca_editada.nome} (ID: {peca_editada.pk})"
            registrar_log(request.user, 'ATUALIZAÇÃO', log_detalhe)

            # MENSAGEM ADICIONADA AQUI
            messages.success(request, f'Peça "{peca_editada.nome}" atualizada com sucesso.')

            return redirect('listar_pecas')
    else: 
        form = PecaForm(instance=peca)

    return render(request, 'cadastros/peca_form.html', {
        'form': form, 
        'peca': peca,
        'titulo': f'Editar Peça: {peca.nome}',
        'is_edit': True
    })


@login_required
@never_cache
def remover_imagem_peca(request, pk):
    peca = get_object_or_404(Peca, pk=pk)
    if peca.imagem:
        peca.imagem.delete(save=False)
        peca.imagem = None
        peca.save()
        registrar_log(request.user, 'ATUALIZAÇÃO', f"Imagem da peça '{peca.nome}' foi removida.")
        
        # MENSAGEM ADICIONADA AQUI
        # Esta mensagem será exibida na página de 'editar_peca'
        messages.success(request, f'Imagem da peça "{peca.nome}" foi removida.')

    # Corrigido: redireciona de volta para a edição
    return redirect('editar_peca', pk=peca.pk) 


@login_required
@permission_required('cadastros.delete_peca', login_url='/acesso-negado/')
@never_cache
def excluir_peca(request, pk):
    peca = get_object_or_404(Peca, pk=pk)

    if request.method == 'POST':
        try:
            nome_peca = peca.nome 
            peca.delete()
            registrar_log(request.user, 'EXCLUSÃO', f"Excluiu a peça: {nome_peca} (ID: {pk})")
            
            # MENSAGEM ADICIONADA AQUI
            messages.success(request, f'Peça "{nome_peca}" foi excluída com sucesso.')
            
            return redirect('listar_pecas')

        except ProtectedError:
            pecas_utilizadas_qs = PecaUtilizada.objects.filter(peca=peca).select_related('ordem_servico')
            os_ids_referentes = sorted(list(set([pu.ordem_servico.pk for pu in pecas_utilizadas_qs]))) 
            os_ids_str = ", ".join(map(str, os_ids_referentes))
            
            mensagem_erro = (
                f'Não é possível excluir la peça "{peca.nome}" porque ela está sendo utilizada '
                f'na(s) seguinte(s) Ordem(ns) de Serviço: #{os_ids_str}. '
                'Por favor, remova a peça dessa(s) OS antes de tentar excluí-la novamente.'
            )
            
            messages.error(request, mensagem_erro) # Você já tinha o 'error' aqui
            return redirect('listar_pecas')
            
        except Exception as e: 
            print(f"Erro inesperado ao excluir peça {pk}: {e}") 
            messages.error(request, f'Ocorreu um erro inesperado ao tentar excluir a peça.') # E aqui também
            return redirect('listar_pecas')

    contexto = {
        'object': peca, 
        'tipo': 'Peça' 
    }
    return render(request, 'cadastros/excluir_confirm.html', contexto)

# --- CRUD de Ordens de Serviço ---
@login_required
@permission_required('cadastros.view_ordemservico', login_url='/acesso-negado/')
@never_cache # <-- ADICIONADO
def listar_ordens_servico(request):
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    data_inicio = request.GET.get('data_inicio', '')

    ordens = OrdemServico.objects.all()

    # Aplicar filtros
    if search_query:
        query = Q(veiculo__cliente__nome__icontains=search_query) | Q(veiculo__placa__icontains=search_query)
        if search_query.isdigit():
            query.add(Q(id=search_query), Q.OR)
        ordens = ordens.filter(query).distinct()

    if status_filter:
        ordens = ordens.filter(status_aprovacao=status_filter)

    if data_inicio:
        ordens = ordens.filter(data_abertura__date__gte=data_inicio)

    ordens = ordens.order_by('veiculo__cliente__nome', 'veiculo__placa')
    paginator = Paginator(ordens, 10)
    page_number = request.GET.get('page')
    ordens_page = paginator.get_page(page_number)
    filtros = request.GET

    # Construir query string para paginação
    base_url_params = '&'.join([f'{k}={v}' for k, v in request.GET.items() if k != 'page'])

    context = {
        'page_obj': ordens_page,
        'search_query': search_query,
        'status_filter': status_filter,
        'data_inicio': data_inicio,
        'filtros': filtros,
        'base_url_params': base_url_params
    }

    # Se for uma requisição HTMX, renderiza apenas o partial da tabela
    if request.htmx:
        return render(request, 'cadastros/_tabela_ordens_servico.html', context)

    # Caso contrário, renderiza a página completa
    return render(request, 'cadastros/listar_ordens_servico.html', context)

@login_required
@permission_required('cadastros.add_ordemservico', login_url='/acesso-negado/')
@never_cache # <-- ADICIONADO
def cadastrar_ordem_servico(request):
    if request.method == 'POST':
        form = OrdemServicoForm(request.POST)
        if form.is_valid():
            nova_os = form.save()
            registrar_log(request.user, 'CRIAÇÃO', nova_os)
            return redirect('listar_ordens_servico')
    else:
        form = OrdemServicoForm()
    return render(request, 'cadastros/ordem_servico_form.html', {'form': form})

@login_required
@permission_required('cadastros.change_ordemservico', login_url='/acesso-negado/')
@never_cache
def editar_ordem_servico(request, pk):
    ordem = get_object_or_404(OrdemServico, pk=pk)
    
    status_antigo_finalizada = ordem.finalizada 

    if request.method == 'POST':
        form = OrdemServicoForm(request.POST, request.FILES or None, instance=ordem)
        
        if form.is_valid():
            ordem_salva = form.save(commit=False) 

            # Lógica para data de conclusão ao finalizar/reabrir
            if not status_antigo_finalizada and ordem_salva.finalizada:
                if not ordem_salva.data_conclusao:
                    ordem_salva.data_conclusao = datetime.now()
            elif status_antigo_finalizada and not ordem_salva.finalizada:
                 ordem_salva.data_conclusao = None 
            
            ordem_salva.save() 

            # Continua redirecionando para os detalhes após salvar
            return redirect('ordem_servico_detalhe', pk=ordem.pk)
    else:
        # Quando for GET, cria o formulário preenchido
        form = OrdemServicoForm(instance=ordem)
        

    context = {
        'form': form,
        'ordem': ordem  # Passa o objeto 'ordem' para o template usar no título
    }
    # Renderiza o novo template SIMPLES para edição
    return render(request, 'cadastros/editar_ordem_servico.html', context)

@login_required
@permission_required('cadastros.delete_ordemservico', login_url='/acesso-negado/')
@never_cache # <-- ADICIONADO
def excluir_ordem_servico(request, pk):
    ordem = get_object_or_404(OrdemServico, pk=pk)
    if request.method == 'POST':
        registrar_log(request.user, 'EXCLUSÃO', ordem)
        ordem.delete()
        return redirect('listar_ordens_servico')
    return render(request, 'cadastros/excluir_confirm.html', {'obj': ordem, 'tipo': 'Ordem de Serviço'})

# --- Gestão de Funcionários ---
@login_required
@permission_required('auth.view_user', login_url='/acesso-negado/')
@never_cache # <-- ADICIONADO
def listar_funcionarios(request):
    status = request.GET.get('status', 'ativo')
    search_query = request.GET.get('q', '')
    if status == 'inativo':
        funcionarios_list = User.objects.filter(is_superuser=False, is_active=False)
    else:
        funcionarios_list = User.objects.filter(is_superuser=False, is_active=True)
    if search_query:
        funcionarios_list = funcionarios_list.filter(
            Q(first_name__icontains=search_query) | Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) | Q(email__icontains=search_query)
        )
    funcionarios_list = funcionarios_list.order_by('username')
    paginator = Paginator(funcionarios_list, 10)
    page_number = request.GET.get('page')
    funcionarios_page = paginator.get_page(page_number)
    context = {'page_obj': funcionarios_page, 'search_query': search_query, 'status': status}

    # Se for uma requisição HTMX, renderiza apenas o partial da tabela
    if request.htmx:
        return render(request, 'cadastros/_tabela_funcionarios.html', context)

    # Caso contrário, renderiza a página completa
    return render(request, 'cadastros/listar_funcionarios.html', context)

@login_required
@permission_required('cadastros.add_ordemservico', login_url='/acesso-negado/')
@never_cache
def cadastrar_ordem_servico(request):
    if request.method == 'POST':
        form = OrdemServicoForm(request.POST)
        if form.is_valid():
            nova_os = form.save()
            registrar_log(request.user, 'CRIAÇÃO', nova_os)
            
            # MENSAGEM ADICIONADA AQUI
            messages.success(request, f'Ordem de Serviço #{nova_os.pk} cadastrada com sucesso!')
            
            return redirect('listar_ordens_servico')
    else:
        form = OrdemServicoForm()
    return render(request, 'cadastros/ordem_servico_form.html', {'form': form})

@login_required
@permission_required('cadastros.change_ordemservico', login_url='/acesso-negado/')
@never_cache
def editar_ordem_servico(request, pk):
    ordem = get_object_or_404(OrdemServico, pk=pk)
    
    status_antigo_finalizada = ordem.finalizada 

    if request.method == 'POST':
        form = OrdemServicoForm(request.POST, request.FILES or None, instance=ordem)
        
        if form.is_valid():
            ordem_salva = form.save(commit=False) 

            # Lógica para data de conclusão ao finalizar/reabrir
            if not status_antigo_finalizada and ordem_salva.finalizada:
                if not ordem_salva.data_conclusao:
                    ordem_salva.data_conclusao = datetime.now()
            elif status_antigo_finalizada and not ordem_salva.finalizada:
                 ordem_salva.data_conclusao = None 
            
            ordem_salva.save() 
            
            # MENSAGEM ADICIONADA AQUI
            # Esta mensagem aparecerá na tela de 'detalhe'
            messages.success(request, f'Ordem de Serviço #{ordem_salva.pk} atualizada com sucesso.')

            # Continua redirecionando para os detalhes após salvar
            return redirect('ordem_servico_detalhe', pk=ordem.pk)
    else:
        # Quando for GET, cria o formulário preenchido
        form = OrdemServicoForm(instance=ordem)

    context = {
        'form': form,
        'ordem': ordem  # Passa o objeto 'ordem' para o template usar no título
    }
    # Renderiza o novo template SIMPLES para edição
    return render(request, 'cadastros/editar_ordem_servico.html', context)

@login_required
@permission_required('cadastros.delete_ordemservico', login_url='/acesso-negado/')
@never_cache
def excluir_ordem_servico(request, pk):
    ordem = get_object_or_404(OrdemServico, pk=pk)
    if request.method == 'POST':
        # Salva o PK para usar na mensagem após o 'delete'
        os_pk = ordem.pk 
        registrar_log(request.user, 'EXCLUSÃO', ordem)
        ordem.delete()
        
        # MENSAGEM ADICIONADA AQUI
        messages.success(request, f'Ordem de Serviço #{os_pk} foi excluída com sucesso.')
        
        return redirect('listar_ordens_servico')
    return render(request, 'cadastros/excluir_confirm.html', {'obj': ordem, 'tipo': 'Ordem de Serviço'})

@login_required
@permission_required('auth.add_user', login_url='/acesso-negado/')
@never_cache
def cadastrar_funcionario(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            novo_func = form.save()
            registrar_log(request.user, 'CRIAÇÃO', f"Funcionário '{novo_func.username}'")
            
            # MENSAGEM ADICIONADA AQUI
            messages.success(request, f'Funcionário "{novo_func.username}" cadastrado com sucesso!')
            
            return redirect('listar_funcionarios')
    else:
        form = CustomUserCreationForm()
    return render(request, 'cadastros/adicionar_funcionario.html', {'form': form})

@login_required
@permission_required('auth.change_user', login_url='/acesso-negado/')
@never_cache
def editar_funcionario(request, pk):
    funcionario = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=funcionario)
        if form.is_valid():
            func_editado = form.save()
            registrar_log(request.user, 'ATUALIZAÇÃO', f"Funcionário '{func_editado.username}'")
            
            # MENSAGEM ADICIONADA AQUI
            messages.success(request, f'Dados do funcionário "{func_editado.username}" atualizados com sucesso.')
            
            return redirect('listar_funcionarios')
    else:
        form = CustomUserChangeForm(instance=funcionario)
    return render(request, 'cadastros/editar_funcionario.html', {'form': form, 'funcionario': funcionario})

@login_required
@permission_required('auth.delete_user', login_url='/acesso-negado/')
@never_cache
def excluir_funcionario(request, pk):
    funcionario = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        # Salva o username para a mensagem
        nome_func = funcionario.username
        registrar_log(request.user, 'EXCLUSÃO', f"Desativação do funcionário '{funcionario.username}'")
        funcionario.is_active = False
        funcionario.save()
        
        # MENSAGEM ADICIONADA AQUI
        messages.success(request, f'O funcionário "{nome_func}" foi desativado com sucesso.') # Usei warning para destacar que foi desativação
        
        return redirect('listar_funcionarios')
    return render(request, 'cadastros/excluir_funcionario.html', {'object': funcionario})

@login_required
@permission_required('auth.view_user', login_url='/acesso-negado/')
@never_cache # <-- ADICIONADO
def listar_funcionarios_inativos(request):
    search_query = request.GET.get('q', '')

    # Inicia com o filtro original da sua view
    funcionarios_inativos = User.objects.filter(is_superuser=False, is_active=False)

    if search_query:
        # Filtra por nome, sobrenome, username OU email
        funcionarios_inativos = funcionarios_inativos.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    funcionarios_inativos = funcionarios_inativos.order_by('username')

    paginator = Paginator(funcionarios_inativos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query
    }

    # Se for uma requisição HTMX, renderiza apenas o partial da tabela
    if request.htmx:
        return render(request, 'cadastros/_tabela_funcionarios_inativos.html', context)

    # Caso contrário, renderiza a página completa
    return render(request, 'cadastros/listar_funcionarios_inativos.html', context)

@login_required
@permission_required('auth.change_user', login_url='/acesso-negado/')
@never_cache
def reativar_funcionario(request, pk):
    funcionario = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        # Salva o nome para usar na mensagem
        nome_func = funcionario.username 
        registrar_log(request.user, 'ATUALIZAÇÃO', f"Reativação do funcionário '{funcionario.username}'")
        funcionario.is_active = True
        funcionario.save()
        
        # MENSAGEM ADICIONADA AQUI
        messages.success(request, f'O funcionário "{nome_func}" foi reativado com sucesso.')
        
        return redirect('listar_funcionarios_inativos')
    return render(request, 'cadastros/reativar_funcionario.html', {'funcionario': funcionario})


@login_required
@permission_required('auth.change_user', login_url='/acesso-negado/')
@never_cache
def gerenciar_privilegios(request):
    
    # --- BLOCO POST (SALVAR) ---
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user = get_object_or_404(User, pk=user_id)
        
        # 1. Limpa todas as permissões do usuário antes de readicionar
        user.user_permissions.clear()

        perm_types = ['view', 'add', 'change', 'delete'] # Ordem das colunas

        # 2. Loop pelos Modelos Padrão
        for model_label, info in RELEVANT_MODELS_MAP.items():
            model_class = info["class"]
            template_name = info["template_name"]
            
            app_label = model_class._meta.app_label
            model_name_lower = model_class._meta.model_name

            for perm_type in perm_types:
                # Reconstrói o nome do input HTML (ex: perm_OrdemServico_view)
                input_name = f"perm_{template_name}_{perm_type}"

                # Se o checkbox veio marcado no POST...
                if input_name in request.POST:
                    codename = f"{perm_type}_{model_name_lower}"
                    try:
                        perm = Permission.objects.get(
                            content_type__app_label=app_label,
                            codename=codename
                        )
                        user.user_permissions.add(perm)
                        print(f"[OK] Adicionado: {codename}")
                    except Permission.DoesNotExist:
                        print(f"[ERRO] Permissão não encontrada: {codename}")
                        continue
        
        # 3. Loop pelas Permissões Customizadas
        for model_label, info in CUSTOM_PERMS_MAP.items():
            template_name = info["template_name"]
            perm_type = info["perm_type"]
            input_name = f"perm_{template_name}_{perm_type}"

            if input_name in request.POST:
                try:
                    # Pega o ContentType do modelo real (ConfiguracoesGerais)
                    content_type = ContentType.objects.get_for_model(info["attached_to_model"])
                    
                    perm = Permission.objects.get(
                        content_type=content_type,
                        codename=info["codename"]
                    )
                    user.user_permissions.add(perm)
                    print(f"[OK] Customizado: {info['codename']}")
                except Exception as e:
                    print(f"[ERRO] Falha na permissão customizada {model_label}: {e}")
                    pass

        # Atualiza a sessão se o usuário estiver alterando o próprio perfil
        if request.user == user:
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)

        messages.success(request, f"Permissões de {user.username} atualizadas com sucesso.")
        return redirect('gerenciar_privilegios')

    # --- BLOCO GET (CARREGAR A PÁGINA) ---
    # ATENÇÃO: Este código está FORA do 'if POST'. Ele roda sempre que não for POST.
    
    funcionarios = User.objects.filter(is_superuser=False, is_active=True).prefetch_related('user_permissions')

    # Combina as listas de labels para o template
    perm_models_labels = list(RELEVANT_MODELS_MAP.keys()) + list(CUSTOM_PERMS_MAP.keys())
    
    # Cria mapa de nomes de template para o HTML
    perm_models_classes = {}
    for label, info in RELEVANT_MODELS_MAP.items():
        perm_models_classes[label] = info["template_name"]
    for label, info in CUSTOM_PERMS_MAP.items():
        perm_models_classes[label] = info["template_name"]

    # Monta dicionário de checkbox marcados
    permissions_data = {}
    for func in funcionarios:
        permissions_data[func.pk] = {}
        user_perms_codenames = func.user_permissions.values_list('codename', flat=True)

        # Checa Modelos Padrão
        for model_label, info in RELEVANT_MODELS_MAP.items():
            permissions_data[func.pk][model_label] = {}
            model_name_lower = info["class"]._meta.model_name
            for perm_type in ['view', 'add', 'change', 'delete']:
                codename = f"{perm_type}_{model_name_lower}"
                permissions_data[func.pk][model_label][perm_type] = (codename in user_perms_codenames)
        
        # Checa Customizadas
        for model_label, info in CUSTOM_PERMS_MAP.items():
            if model_label not in permissions_data[func.pk]:
                permissions_data[func.pk][model_label] = {}
            
            codename = info["codename"]
            perm_type = info["perm_type"]
            permissions_data[func.pk][model_label][perm_type] = (codename in user_perms_codenames)

    context = {
        'funcionarios': funcionarios, 
        'permissions_data': permissions_data,
        'perm_models_classes': perm_models_classes, 
        'perm_models_labels': perm_models_labels,
        'perm_types': ['view', 'add', 'change', 'delete'],
    }
    
    # 🔥 CORREÇÃO PRINCIPAL: O return está alinhado à esquerda (nível da função)
    return render(request, 'cadastros/gerenciar_privilegios.html', context)

# --- Detalhes e Peças da OS ---
@login_required
@permission_required('cadastros.view_ordemservico', login_url='/acesso-negado/')
@never_cache
def ordem_servico_detalhe(request, pk):
    ordem = get_object_or_404(OrdemServico, pk=pk)
    pecas_utilizadas = ordem.pecas_utilizadas.all()
    contexto = {'ordem': ordem, 'pecas_utilizadas': pecas_utilizadas}
    return render(request, 'cadastros/ordem_servico_detalhe.html', contexto)

@login_required
@permission_required('cadastros.change_ordemservico', login_url='/acesso-negado/')
@never_cache
def finalizar_ordem_servico(request, pk):
    ordem = get_object_or_404(OrdemServico, pk=pk)
    if request.method == 'POST':
        mensagem_sucesso = "" # Variável para guardar a mensagem
        
        if ordem.finalizada:
            # Reabrir OS Principal
            ordem.finalizada = False
            ordem.data_conclusao = None
            ordem.status_aprovacao = 'AGUARDANDO' 
            registrar_log(request.user, 'ATUALIZAÇÃO', f'Reabriu {ordem}')
            # Define a mensagem
            mensagem_sucesso = f'Ordem de Serviço #{ordem.pk} foi REABERTA com sucesso.'
        else:
            # Finalizar OS Principal
            ordem.finalizada = True
            if not ordem.data_conclusao:
                ordem.data_conclusao = datetime.now()
            ordem.status_aprovacao = 'FINALIZADO'
            registrar_log(request.user, 'ATUALIZAÇÃO', f'Finalizou {ordem}')
            # Define a mensagem
            mensagem_sucesso = f'Ordem de Serviço #{ordem.pk} foi FINALIZADA com sucesso.'
            
        ordem.save()
        
        # MENSAGEM ADICIONADA AQUI (usando a variável)
        messages.success(request, mensagem_sucesso)
        
    return redirect('ordem_servico_detalhe', pk=pk)

@login_required
@permission_required('cadastros.change_ordemservico', login_url='/acesso-negado/')
@never_cache
def alterar_status_aprovacao(request, pk):
    ordem = get_object_or_404(OrdemServico, pk=pk)

    if request.method == 'POST':
        novo_status = request.POST.get('status_aprovacao')
        if novo_status in ['AGUARDANDO', 'APROVADO', 'REPROVADO', 'FINALIZADO']:
            status_antigo = ordem.get_status_aprovacao_display()
            ordem.status_aprovacao = novo_status

            # (Lógica de finalizar/reabrir OS)
            if novo_status == 'FINALIZADO' or novo_status == 'REPROVADO':
                if not ordem.finalizada:
                    ordem.finalizada = True
                    if not ordem.data_conclusao:
                        ordem.data_conclusao = datetime.now()
                    registrar_log(request.user, 'ATUALIZAÇÃO', f'Finalizou {ordem} via alteração de status para {ordem.get_status_aprovacao_display()}')
            
            elif ordem.finalizada and novo_status not in ['FINALIZADO', 'REPROVADO']:
                 ordem.finalizada = False
                 ordem.data_conclusao = None
                 registrar_log(request.user, 'ATUALIZAÇÃO', f'Reabriu {ordem} via alteração de status para {ordem.get_status_aprovacao_display()}')
            
            registrar_log(request.user, 'ATUALIZAÇÃO', f'Alterou status de aprovação de {ordem} para {ordem.get_status_aprovacao_display()}')
            ordem.save()
            
            # MENSAGEM ADICIONADA AQUI
            # Pega o nome "bonito" do status (ex: "Aprovado")
            novo_status_display = ordem.get_status_aprovacao_display() 
            messages.success(request, f'Status da OS #{ordem.pk} alterado para "{novo_status_display}".')

        # --- CORREÇÃO: O redirect deve estar AQUI, no final do bloco POST ---
        return redirect('ordem_servico_detalhe', pk=pk)

    return redirect('ordem_servico_detalhe', pk=pk)

@login_required
@permission_required('cadastros.add_pecautilizada', login_url='/acesso-negado/')
@never_cache
def adicionar_peca_na_os(request, ordem_id, peca_id=None): # peca_id opcional para GET inicial
    ordem = get_object_or_404(OrdemServico, pk=ordem_id)
    peca_selecionada = None
    if peca_id:
        peca_selecionada = get_object_or_404(Peca, pk=peca_id)

    pecas_disponiveis = Peca.objects.filter(quantidade__gt=0).order_by('nome') 

    if request.method == 'POST':
        form = PecaUtilizadaForm(request.POST)
        if form.is_valid():
            peca_id_form = request.POST.get('peca')
            quantidade_a_usar = form.cleaned_data['quantidade_utilizada']
            
            try:
                peca = Peca.objects.get(pk=peca_id_form)

                if quantidade_a_usar > peca.quantidade:
                    # MENSAGEM DE ERRO (JÁ EXISTIA)
                    messages.error(request, f"Quantidade indisponível em estoque para '{peca.nome}'. Disponível: {peca.quantidade}")
                else:
                    peca_utilizada, created = PecaUtilizada.objects.get_or_create(
                        ordem_servico=ordem,
                        peca=peca,
                        defaults={'quantidade_utilizada': 0} 
                    )
                    
                    quantidade_anterior_usada = peca_utilizada.quantidade_utilizada if not created else 0
                    
                    peca_utilizada.quantidade_utilizada += quantidade_a_usar
                    peca_utilizada.save()

                    peca.quantidade -= quantidade_a_usar
                    peca.save() 

                    # (lógica de alerta de estoque)
                    if getattr(peca, 'deve_enviar_alerta', False):
                        print(f"View (adicionar_peca_na_os): Alerta detectado para {peca.nome}. Enviando para {request.user.email}")
                        peca.enviar_email_de_alerta_para_usuario(request.user)

                    acao_log = "Adicionou" if created else f"Atualizou quantidade para {peca_utilizada.quantidade_utilizada} (adicionou {quantidade_a_usar})"
                    registrar_log(request.user, 'CRIAÇÃO' if created else 'ATUALIZAÇÃO', 
                                  f"{acao_log} peça '{peca.nome}' na {ordem}")
                    
                    # MENSAGEM DE SUCESSO (JÁ EXISTIA)
                    messages.success(request, f"Peça '{peca.nome}' ({quantidade_a_usar} un.) adicionada/atualizada na OS.")
                    
                    return redirect('ordem_servico_detalhe', pk=ordem_id)

            except Peca.DoesNotExist:
                # MENSAGEM DE ERRO (JÁ EXISTIA)
                messages.error(request, "Peça selecionada não encontrada.")
            except Exception as e:
                # MENSAGEM DE ERRO (JÁ EXISTIA)
                messages.error(request, f"Ocorreu um erro: {e}")

    else: # GET Request
        initial_data = {}
        if peca_selecionada:
            initial_data['peca'] = peca_selecionada.pk
        form = PecaUtilizadaForm(initial=initial_data)

    contexto = {
        'form': form,
        'ordem': ordem,
        'pecas_disponiveis': pecas_disponiveis,
        'peca_selecionada': peca_selecionada, 
    }
    return render(request, 'cadastros/adicionar_peca_na_os.html', contexto)

@login_required
@permission_required('cadastros.change_ordemservico', login_url='/acesso-negado/')
@never_cache
def remover_peca_da_os(request, pk):
    peca_utilizada = get_object_or_404(PecaUtilizada, pk=pk)
    ordem = peca_utilizada.ordem_servico
    if request.method == 'POST':
        peca = peca_utilizada.peca
        
        # Salva dados para a mensagem ANTES de deletar
        nome_peca = peca.nome
        qtd_removida = peca_utilizada.quantidade_utilizada
        
        peca.quantidade += peca_utilizada.quantidade_utilizada
        peca.save()
        registrar_log(request.user, 'ATUALIZAÇÃO', f"Removeu {qtd_removida}x '{nome_peca}' da {ordem}")
        peca_utilizada.delete()
        
        # MENSAGEM ADICIONADA AQUI
        messages.success(request, f'Peça "{nome_peca}" ({qtd_removida} un.) foi removida da OS #{ordem.pk}.')
        
        return redirect('ordem_servico_detalhe', pk=ordem.pk)
    contexto = {'obj': peca_utilizada, 'tipo': 'Peça da Ordem de Serviço'}
    return render(request, 'cadastros/excluir_confirm.html', contexto)

# --- (NOVAS VIEWS DE SERVIÇOS, ANEXOS, PDF, CONFIGS) ---
@login_required
@permission_required('cadastros.change_ordemservico', login_url='/acesso-negado/')
@never_cache
def adicionar_servico_na_os(request, ordem_id):
    ordem = get_object_or_404(OrdemServico, pk=ordem_id)

    if request.method == 'POST':
        form = ServicoUtilizadoForm(request.POST)
        if form.is_valid():
            servico = form.save(commit=False)
            servico.ordem_servico = ordem
            servico.save()
            registrar_log(request.user, 'ATUALIZAÇÃO', f"Adicionou serviço '{servico.descricao}' à {ordem}")
            
            # MENSAGEM ADICIONADA AQUI
            messages.success(request, f'Serviço "{servico.descricao}" foi adicionado com sucesso.')
            
            return redirect('ordem_servico_detalhe', pk=ordem_id)
    else:
        form = ServicoUtilizadoForm()

    contexto = {'form': form, 'ordem': ordem}
    return render(request, 'cadastros/adicionar_servico_na_os.html', contexto)

@login_required
@permission_required('cadastros.change_ordemservico', login_url='/acesso-negado/')
@never_cache
def remover_servico_da_os(request, pk):
    servico_utilizado = get_object_or_404(ServicoUtilizado, pk=pk)
    ordem = servico_utilizado.ordem_servico

    if request.method == 'POST':
        descricao = servico_utilizado.descricao
        registrar_log(request.user, 'ATUALIZAÇÃO', f"Removeu serviço '{descricao}' da {ordem}")
        servico_utilizado.delete()
        
        # MENSAGEM ADICIONADA AQUI
        messages.success(request, f'Serviço "{descricao}" foi removido com sucesso.')
        
        return redirect('ordem_servico_detalhe', pk=ordem.pk)

    contexto = {'obj': servico_utilizado, 'tipo': 'Serviço da Ordem de Serviço'}
    return render(request, 'cadastros/excluir_confirm.html', contexto)

@login_required
@permission_required('cadastros.change_ordemservico', login_url='/acesso-negado/')
def adicionar_anexo_na_os(request, ordem_id):
    ordem = get_object_or_404(OrdemServico, pk=ordem_id)
    
    if request.method == 'POST':
        form = AnexoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                anexo = form.save(commit=False)
                anexo.ordem_servico = ordem
                anexo.save()
                registrar_log(request.user, 'CRIAÇÃO', f"Adicionou anexo '{anexo.arquivo.name}' à {ordem}")
                
                # MENSAGEM DE SUCESSO ADICIONADA
                messages.success(request, f'Anexo "{anexo.arquivo.name}" foi adicionado com sucesso.')
                
                return redirect('ordem_servico_detalhe', pk=ordem_id)
            except Exception as e: 
                # MENSAGEM DE ERRO ADICIONADA
                messages.error(request, f"Erro ao salvar anexo: {e}")
                print(f"Erro ao salvar anexo para OS {ordem_id}: {e}") 
        # Se o form NÃO for válido, a execução continua e renderiza o template com o form contendo erros
            
    else: # GET Request
        form = AnexoForm() 

    contexto = {
        'form': form, # Passa o form (novo ou com erros) para o template
        'ordem': ordem,
        'color_classes': get_primary_color_classes(), # Mantenha se a função existir
    }
    return render(request, 'cadastros/adicionar_anexo_na_os.html', contexto)

# View para remover anexo
@login_required
@permission_required('cadastros.delete_anexoordemservico', login_url='/acesso-negado/')
@never_cache
def remover_anexo_da_os(request, pk):
    anexo = get_object_or_404(AnexoOrdemServico, pk=pk)
    ordem = anexo.ordem_servico 

    if request.method == 'POST':
        try:
            nome_arquivo = anexo.arquivo.name 
            caminho_arquivo = anexo.arquivo.path 
            
            # 1. Deletar o registro do banco de dados
            anexo.delete()

            # 2. Tentar deletar o arquivo físico (Opcional - como no seu código)
            # ...

            registrar_log(request.user, 'EXCLUSÃO', f"Removeu anexo '{nome_arquivo}' da {ordem}")
            
            # MENSAGEM DE SUCESSO ADICIONADA
            messages.success(request, f'Anexo "{nome_arquivo}" foi removido com sucesso.')
            
            return redirect('ordem_servico_detalhe', pk=ordem.pk)
        
        except Exception as e:
            # MENSAGEM DE ERRO ADICIONADA
            messages.error(request, f"Erro ao remover o anexo: {e}")
            print(f"Erro ao remover anexo {pk} da OS {ordem.pk}: {e}") 
            
            return redirect('ordem_servico_detalhe', pk=ordem.pk)

    # Se a requisição for GET, mostra a página de confirmação
    contexto = {
        'object': anexo, 
        'ordem': ordem, 
        'tipo': f'Anexo ({anexo.arquivo.name}) da Ordem de Serviço #{ordem.pk}'
    }
    return render(request, 'cadastros/excluir_confirm.html', contexto)


# --- Sua View ---
@login_required
@permission_required('cadastros.view_ordemservico', login_url='/acesso-negado/')
@never_cache
def gerar_os_pdf(request, pk):
    os_obj = get_object_or_404(OrdemServico.objects.select_related('veiculo__cliente'), pk=pk)
    pecas = os_obj.pecas_utilizadas.select_related('peca').all()
    servicos = os_obj.servicos_utilizados.all()
    config = ConfiguracoesGerais.objects.first()

    template_path = 'cadastros/os_template_pdf.html' # Caminho para o seu template HTML
    context = {
        'os': os_obj,
        'pecas_utilizadas': pecas,
        'servicos_utilizados': servicos,
        'config': config,
         # Adicione as cores primárias/secundárias ao contexto se o CSS as usar diretamente
        # 'cor_primaria': config.cor_primaria if config else '#0d6efd',
        # 'cor_secundaria': config.cor_secundaria if config else '#10B981',
    }

    # Cria a resposta HTTP com o tipo de conteúdo PDF
    response = HttpResponse(content_type='application/pdf')
    # Define o cabeçalho para abrir inline ou baixar
    response['Content-Disposition'] = f'inline; filename="os_{os_obj.pk}.pdf"'
    # Encontra o template e renderiza
    template = get_template(template_path)
    html = template.render(context)

    # Cria o PDF
    pisa_status = pisa.CreatePDF(
       html.encode('UTF-8'), dest=response, encoding='UTF-8') # Adiciona encoding

    # Retorna erro se o PDF falhar
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


@login_required
@permission_required('cadastros.view_configuracoesgerais', login_url='/acesso-negado/') 
@never_cache
def configuracoes(request):
    # Pega a configuração existente (pk=1) ou cria uma com valores padrão
    config, created = ConfiguracoesGerais.objects.get_or_create(
        pk=1,
        defaults={'nome_empresa': 'Nome Padrão'}
    )

    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' # Detecta AJAX ou HTMX
        
        # Passa os dados do POST e os arquivos para o form, usando a instância existente
        form = ConfiguracoesGeraisForm(request.POST, request.FILES, instance=config)
        
        if form.is_valid():
            # Salva o objeto primeiro para ter as novas URLs e cores
            config = form.save() 
            registrar_log(request.user, 'ATUALIZAÇÃO', 'Atualizou configurações gerais do sistema')
            
            # --- NOVO BLOCO PARA RESPOSTA AJAX PURA (JSON) ---
            if is_ajax and not request.htmx:
                # Constrói o dicionário de URLs/dados atualizados
                data = {
                    'success': True,
                    'nome_empresa': config.nome_empresa,
                    'urls': {
                        # Retorna a URL completa da imagem salva ou None/string vazia
                        'logo_url': config.logo.url if config.logo else None,
                        'imagem_fundo_url': config.imagem_fundo.url if config.imagem_fundo else 'https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?q=80&w=1920&auto=format&fit=crop',
                        'cor_primaria': config.cor_primaria,
                        'cor_secundaria': config.cor_secundaria,
                    }
                }
                # Retorna a resposta JSON esperada pelo JS
                return JsonResponse(data)
            
            # --- BLOCO HTMX EXISTENTE (MANTER SE VOCÊ AINDA USA HTMX) ---
            if request.htmx:
                return render(request, 'cadastros/_mensagem_sucesso.html', {
                    'mensagem': 'Configurações salvas com sucesso!',
                    'redirect_url': reverse('configuracoes')
                })
                
            # --- RESPOSTA PADRÃO (SE NÃO FOR AJAX NEM HTMX) ---
            return redirect('configuracoes') # Redireciona para a mesma view (GET)
            
        else:
            # --- NOVO BLOCO PARA ERRO AJAX PURA (JSON com status 400) ---
            # Se for AJAX e houver erros, retornamos JSON com o formulário em HTML
            if is_ajax and not request.htmx:
                 # Renderiza o formulário com erros para retornar o HTML ao front-end
                 # O JS irá analisar e substituir o container, mantendo o estado 400.
                 # (Manteremos a lógica de retorno de HTML para facilitar a exibição dos erros)
                 contexto = {
                    'form': form,
                    'configuracoes': config,
                    'color_classes': get_primary_color_classes(),
                 }
                 html_content = render_to_string('cadastros/configuracoes.html', contexto, request=request)
                 return HttpResponse(html_content, status=400)


            # --- BLOCO HTMX EXISTENTE ---
            if request.htmx:
                return render(request, 'cadastros/_form_erros.html', {
                    'form': form,
                    'hx_post_url': reverse('configuracoes'),
                    'cancel_url': reverse('configuracoes')
                })
                
            # Se o form NÃO for válido (e não for AJAX/HTMX), renderiza o template com o formulário de erros.
            
    else: # GET Request
        # Cria um formulário preenchido com os dados da instância 'config'
        form = ConfiguracoesGeraisForm(instance=config)

    contexto = {
        'form': form, 
        'configuracoes': config, 
        'color_classes': get_primary_color_classes(),
    }
    return render(request, 'cadastros/configuracoes.html', contexto)

# --- Helper function for filtering logs ---
def _get_filtered_logs_qs(request):
    acao_filter = request.GET.get('acao')
    usuario_filter = request.GET.get('usuario', '')

    logs_qs = LogAtividade.objects.all().order_by('-data_hora')

    if acao_filter:
        logs_qs = logs_qs.filter(acao__iexact=acao_filter)

    if usuario_filter:
        logs_qs = logs_qs.filter(
            Q(usuario__first_name__icontains=usuario_filter) |
            Q(usuario__last_name__icontains=usuario_filter) |
            Q(usuario__username__icontains=usuario_filter)
        )

    return logs_qs

# --- Log de Atividades ---
@login_required
@permission_required('cadastros.view_logatividade', login_url='/acesso-negado/')
@never_cache
def listar_log_atividades(request):

    if request.method == 'POST':
        # --- LÓGICA DE EXCLUSÃO (POST) ---
        # NENHUMA ALTERAÇÃO AQUI. 
        # Este fluxo de confirmação/redirect ainda causará um recarregamento
        # de página, o que é esperado para este tipo de ação complexa
        # (a menos que seja refatorado para um modal HTMX).

        # Verifica se é confirmação de exclusão
        if request.POST.get('confirm_delete'):
            selected_logs_ids = request.POST.getlist('selected_logs')
            delete_all = request.POST.get('delete_all') == 'true'

            if delete_all:
                # Excluir todos os logs filtrados
                acao_filter = request.POST.get('acao')
                usuario_filter = request.POST.get('usuario')
                logs_to_delete = LogAtividade.objects.all()
                if acao_filter:
                    logs_to_delete = logs_to_delete.filter(acao=acao_filter)
                if usuario_filter:
                    logs_to_delete = logs_to_delete.filter(
                        Q(usuario__first_name__icontains=usuario_filter) |
                        Q(usuario__last_name__icontains=usuario_filter) |
                        Q(usuario__username__icontains=usuario_filter)
                    )
                count_deleted = logs_to_delete.count()
                logs_to_delete.delete()
                registrar_log(request.user, 'EXCLUSÃO', f'Excluiu todos os logs de atividades ({count_deleted} registros)')
            else:
                # Excluir logs selecionados
                logs_to_delete = LogAtividade.objects.filter(id__in=selected_logs_ids)
                count_deleted = logs_to_delete.count()
                logs_to_delete.delete()
                registrar_log(request.user, 'EXCLUSÃO', f'Excluiu {count_deleted} logs de atividades selecionados')

            # Redireciona de volta para a lista com os filtros aplicados
            filtros = request.POST.copy()
            filtros.pop('csrfmiddlewaretoken', None)
            filtros.pop('selected_logs', None)
            filtros.pop('delete_all', None)
            filtros.pop('confirm_delete', None)
            query_string = '&'.join([f'{k}={v}' for k, v in filtros.items() if v])
            url = reverse('listar_log_atividades')
            return redirect(f"{url}?{query_string}" if query_string else url)

        # Se não é confirmação, é solicitação de exclusão - redirecionar para confirmação
        selected_logs_ids = request.POST.getlist('selected_logs')
        delete_all = request.POST.get('delete_all') == 'true'

        if delete_all:
            # Para exclusão de todos, obter os logs filtrados
            acao_filter = request.GET.get('acao')
            usuario_filter = request.GET.get('usuario')
            logs_to_delete = LogAtividade.objects.all()
            if acao_filter:
                logs_to_delete = logs_to_delete.filter(acao=acao_filter)
            if usuario_filter:
                logs_to_delete = logs_to_delete.filter(
                    Q(usuario__first_name__icontains=usuario_filter) |
                    Q(usuario__last_name__icontains=usuario_filter) |
                    Q(usuario__username__icontains=usuario_filter)
                )
            logs_to_delete = list(logs_to_delete)
        else:
            # Para exclusão selecionada, obter os logs específicos
            logs_to_delete = list(LogAtividade.objects.filter(id__in=selected_logs_ids))

        # Preparar filtros para voltar
        filtros_dict = request.GET.copy()
        if 'page' in filtros_dict:
            del filtros_dict['page']

        context = {
            'logs_to_delete': logs_to_delete,
            'selected_logs': selected_logs_ids,
            'delete_all': delete_all,
            'filtros': filtros_dict,
        }
        return render(request, 'cadastros/confirmar_exclusao_logs.html', context)

    # --- LÓGICA DE LISTAGEM (GET) ---
    # Aqui é onde a correção do HTMX para filtro e paginação é aplicada.

    # 1. Obtenha os parâmetros de filtro (para o formulário)
    acao_filter = request.GET.get('acao')
    usuario_filter = request.GET.get('usuario')

    # 2. Comece com todos os logs
    log_list = LogAtividade.objects.all().select_related('usuario').order_by('-data_hora') # Adicionado ordem

    # 3. Aplique os filtros, se existirem
    if acao_filter:
        log_list = log_list.filter(acao=acao_filter)
    if usuario_filter:
        log_list = log_list.filter(
            Q(usuario__first_name__icontains=usuario_filter) |
            Q(usuario__last_name__icontains=usuario_filter) |
            Q(usuario__username__icontains=usuario_filter)
        )

    # 4. Configure a paginação
    paginator = Paginator(log_list, 20) # (Ajuste '20' para quantos logs quiser por página)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 5. Crie uma cópia dos parâmetros GET atuais para usar nos links
    filtros_dict = request.GET.copy()

    # 6. Remova o parâmetro 'page' para evitar duplicação nos links
    if 'page' in filtros_dict:
        del filtros_dict['page']

    # 7. Passe tudo para o contexto
    context = {
        'page_obj': page_obj,
        'acao_filter': acao_filter,      # Para preencher o <select>
        'usuario_filter': usuario_filter, # Para preencher o <input>
        'filtros': filtros_dict,          # Para a paginação
    }

    # --- A CORREÇÃO ESTÁ AQUI ---
    # Se for uma requisição HTMX (de filtro ou paginação),
    # renderiza APENAS o pedaço da tabela.
    if request.htmx:
        # Assumindo que seu template parcial é '_tabela_logs.html'
        return render(request, 'cadastros/_tabela_logs.html', context)
    
    # Se for uma carga normal (GET), renderiza a página inteira
    return render(request, 'cadastros/log_atividades.html', context)

@login_required
@permission_required('cadastros.view_logatividade', login_url='/acesso-negado/')
@never_cache
def exportar_logs_csv(request):
    logs_qs = _get_filtered_logs_qs(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="logs_atividades.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Usuário', 'Ação', 'Detalhes', 'Data/Hora'])

    for log in logs_qs:
        # ==========================================================
        # ⚡ CORREÇÃO: CONVERTE A HORA UTC DO BANCO PARA O FUSO LOCAL
        
        # 1. Pega o datetime "aware" (UTC) do banco de dados
        data_hora_utc = log.data_hora
        
        # 2. Converte para o fuso local (definido em settings.TIME_ZONE)
        data_hora_local = timezone.localtime(data_hora_utc)
        
        # ==========================================================
        
        writer.writerow([
            log.id,
            log.usuario.username if log.usuario else 'Sistema',
            log.acao,
            log.detalhes,
            # 3. Formata a hora local corrigida
            data_hora_local.strftime('%d/%m/%Y %H:%M:%S')
        ])

    registrar_log(request.user, 'EXPORTAÇÃO', f"Exportou {logs_qs.count()} logs para CSV")
    return response

@login_required
@permission_required('cadastros.add_logatividade', login_url='/acesso-negado/')
@never_cache
def importar_logs_anexo(request):
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, "Nenhum arquivo selecionado.")
            return redirect('importar_logs_anexo')

        if not csv_file.name.endswith('.csv'):
            messages.error(request, "O arquivo deve ter extensão .csv")
            return redirect('importar_logs_anexo')

        try:
            decoded_file = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(decoded_file.splitlines())

            # Pega o fuso local do settings.py (Ex: 'America/Sao_Paulo')
            local_tz = pytz.timezone(settings.TIME_ZONE)

            logs_importados = 0
            for row in csv_reader:
                try:
                    # Tentar encontrar usuário pelo username
                    usuario = None
                    if row.get('Usuário') and row['Usuário'] != 'Sistema':
                        usuario = User.objects.filter(username=row['Usuário']).first()

                    # ==========================================================
                    # ⚡ LÓGICA DE DATA/HORA CORRIGIDA
                    # ==========================================================
                    
                    data_hora_para_salvar = None
                    timestamp_string = row.get('Data/Hora')

                    if timestamp_string:
                        # 1. Se o CSV tem a data, tratamos ela como local
                        data_hora_naive = datetime.strptime(timestamp_string, '%d/%m/%Y %H:%M:%S')
                        # Transforma a data "naive" em "aware" (Ex: 10:00 -> 10:00-03:00)
                        data_hora_para_salvar = local_tz.localize(data_hora_naive)
                    else:
                        # 2. Se o CSV não tem data, pegamos a hora atual "aware"
                        # timezone.now() já retorna a hora correta em UTC (Ex: 13:08 UTC)
                        data_hora_para_salvar = timezone.now()
                    
                    # ==========================================================

                    LogAtividade.objects.create(
                        usuario=usuario,
                        acao=row.get('Ação', ''),
                        detalhes=row.get('Detalhes', ''),
                        # 3. Salva o datetime "aware" (corrigido)
                        data_hora=data_hora_para_salvar 
                    )
                    logs_importados += 1
                except Exception as e:
                    print(f"Erro ao importar linha: {e}")
                    continue

            # (O 'registrar_log' precisa estar definido em algum lugar)
            # registrar_log(request.user, 'IMPORTAÇÃO', f"Importou {logs_importados} logs via CSV")
            
            messages.success(request, f"{logs_importados} logs importados com sucesso.")
            return redirect('listar_log_atividades')
        except Exception as e:
            messages.error(request, f"Erro ao processar arquivo CSV: {e}")
            return redirect('importar_logs_anexo')

    return render(request, 'cadastros/importar_logs_anexo.html')

@login_required
@permission_required('cadastros.add_logatividade', login_url='/acesso-negado/')
@never_cache
def importar_logs_csv(request):
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, "Nenhum arquivo selecionado.")
            return redirect('listar_log_atividades')

        if not csv_file.name.endswith('.csv'):
            messages.error(request, "O arquivo deve ter extensão .csv")
            return redirect('listar_log_atividades')

        try:
            decoded_file = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(decoded_file.splitlines())

            logs_importados = 0
            for row in csv_reader:
                try:
                    # Tentar encontrar usuário pelo username
                    usuario = None
                    if row.get('Usuário') and row['Usuário'] != 'Sistema':
                        usuario = User.objects.filter(username=row['Usuário']).first()

                    LogAtividade.objects.create(
                        usuario=usuario,
                        acao=row.get('Ação', ''),
                        detalhes=row.get('Detalhes', ''),
                        data_hora=datetime.strptime(row.get('Data/Hora', ''), '%d/%m/%Y %H:%M:%S') if row.get('Data/Hora') else datetime.now()
                    )
                    logs_importados += 1
                except Exception as e:
                    print(f"Erro ao importar linha: {e}")
                    continue

            registrar_log(request.user, 'IMPORTAÇÃO', f"Importou {logs_importados} logs via CSV")
            messages.success(request, f"{logs_importados} logs importados com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao processar arquivo CSV: {e}")

    return redirect('listar_log_atividades')

@login_required
def roteador_inicial(request):
    """
    Redireciona o usuário para a primeira página que ele tem permissão de ver,
    evitando a tela de Acesso Negado logo no login.
    """
    user = request.user

    # Lista de prioridades: (Permissão Necessária, Nome da URL de destino)
    # A ordem importa! Ele tentará a primeira, depois a segunda, etc.
    rotas = [
        ('cadastros.view_dashboard', 'home'),
        ('cadastros.view_ordemservico', 'listar_ordens_servico'),
        ('cadastros.view_cliente', 'listar_clientes'),
        ('cadastros.view_veiculo', 'listar_veiculos'),
        ('cadastros.view_peca', 'listar_pecas'),
        ('cadastros.view_funcionario', 'listar_funcionarios'),
        ('cadastros.view_logatividade', 'listar_log_atividades'),
        ('cadastros.change_configuracoesgerais', 'configuracoes'),
    ]

    # Se for superusuário, manda direto pro Dashboard (ou onde você preferir)
    if user.is_superuser:
        return redirect('home')

    # Verifica as permissões na ordem da lista
    for permissao, url_name in rotas:
        if user.has_perm(permissao):
            return redirect(url_name)

    # CENÁRIO FINAL: O usuário logou mas não tem permissão NENHUMA.
    # Nesse caso, enviamos para uma página de "Sem Permissões" ou Acesso Negado.
    # Você pode criar uma view simples que diz "Bem-vindo, aguarde liberação do admin".
    return render(request, 'cadastros/acesso_negado.html')


# ==================== NOVAS VIEWS DO SITE PÚBLICO ====================

def site_home(request):
    """Página inicial pública do site"""
    configuracao = ConfiguracaoSite.carregar()
    servicos = Servico.objects.filter(ativo=True).order_by('ordem', 'nome')
    fotos = FotoTrabalho.objects.all()[:6]  # Últimas 6 fotos
    
    context = {
        'configuracao': configuracao,
        'servicos': servicos,
        'fotos': fotos,
    }
    return render(request, 'site/home.html', context)


def site_servicos(request):
    """Página de listagem de serviços"""
    configuracao = ConfiguracaoSite.carregar()
    servicos = Servico.objects.filter(ativo=True).order_by('ordem', 'nome')
    
    context = {
        'configuracao': configuracao,
        'servicos': servicos,
    }
    return render(request, 'site/servicos.html', context)


def site_agendar(request):
    """Página de agendamento"""
    configuracao = ConfiguracaoSite.carregar()
    servicos = Servico.objects.filter(ativo=True).order_by('ordem', 'nome')
    
    # Obtém horários de funcionamento
    horarios = HorarioFuncionamento.objects.filter(ativo=True).order_by('dia_semana')
    
    # Obtém dias bloqueados
    from datetime import date
    dias_bloqueados = DiaBloqueado.objects.values_list('data', flat=True)
    
    context = {
        'configuracao': configuracao,
        'servicos': servicos,
        'horarios': horarios,
        'dias_bloqueados': list(dias_bloqueados),
    }
    return render(request, 'site/agendar.html', context)


def site_sucesso(request):
    """Página de sucesso após agendamento"""
    configuracao = ConfiguracaoSite.carregar()
    
    context = {
        'configuracao': configuracao,
    }
    return render(request, 'site/sucesso.html', context)


# ==================== VIEWS DO PAINEL ADMIN (AGENDAMENTO) ====================

def admin_dashboard(request):
    """Dashboard do admin/painel do dono"""
    from datetime import date, timedelta
    
    today = date.today()
    
    # Agendamentos de hoje
    agendamentos_hoje = Agendamento.objects.filter(data=today).order_by('horario')
    
    # Total de agendamentos do dia
    total_hoje = agendamentos_hoje.count()
    
    # Agendamentos confirmados
    confirmados_hoje = agendamentos_hoje.filter(status='CONFIRMADO').count()
    
    # Receita do dia (soma dos serviços realizados)
    receita_hoje = 0
    for ag in agendamentos_hoje.filter(status='FINALIZADO'):
        receita_hoje += float(ag.servico.preco)
    
    # Próximos agendamentos (próximos 7 dias)
    proximos = Agendamento.objects.filter(
        data__gte=today,
        data__lte=today + timedelta(days=7)
    ).order_by('data', 'horario')[:10]
    
    # Estatísticas da semana
    semana_passada = today - timedelta(days=7)
    agendamentos_semana = Agendamento.objects.filter(data__gte=semana_passada).count()
    
    # Média de avaliações
    avaliacoes = Agendamento.objects.filter(nota_avaliacao__isnull=False)
    nota_media = 0
    if avaliacoes.exists():
        nota_media = avaliacoes.aggregate(Avg('nota_avaliacao'))['nota_avaliacao__avg']
    
    context = {
        'agendamentos_hoje': agendamentos_hoje,
        'total_hoje': total_hoje,
        'confirmados_hoje': confirmados_hoje,
        'receita_hoje': receita_hoje,
        'proximos': proximos,
        'agendamentos_semana': agendamentos_semana,
        'nota_media': nota_media,
    }
    return render(request, 'site/admin_dashboard.html', context)


def admin_agendamentos(request):
    """Lista de agendamentos para o admin"""
    from datetime import date
    from django.db.models import Q
    
    today = date.today()
    
    # Filtros
    status_filter = request.GET.get('status', '')
    data_filter = request.GET.get('data', '')
    search = request.GET.get('q', '')
    
    agendamentos = Agendamento.objects.all().order_by('-data', '-horario')
    
    if status_filter:
        agendamentos = agendamentos.filter(status=status_filter)
    
    if data_filter:
        agendamentos = agendamentos.filter(data=data_filter)
    
    if search:
        agendamentos = agendamentos.filter(
            Q(cliente_nome__icontains=search) |
            Q(cliente_telefone__icontains=search)
        )
    
    # Paginação
    paginator = Paginator(agendamentos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'data_filter': data_filter,
        'search': search,
    }
    return render(request, 'site/admin_agendamentos.html', context)


def admin_alterar_status(request, pk, status):
    """Altera o status de um agendamento"""
    agendamento = get_object_or_404(Agendamento, pk=pk)
    
    if status in ['AGENDADO', 'CONFIRMADO', 'EM_ANDAMENTO', 'FINALIZADO', 'CANCELADO']:
        agendamento.status = status
        agendamento.save()
        messages.success(request, f'Status do agendamento alterado para {agendamento.get_status_display()}')
    
    return redirect('admin_agendamentos')


def admin_servicos(request):
    """Gestão de serviços"""
    servicos = Servico.objects.all().order_by('ordem', 'nome')
    
    context = {
        'servicos': servicos,
    }
    return render(request, 'site/admin_servicos.html', context)


def admin_horarios(request):
    """Gestão de horários de funcionamento"""
    horarios = HorarioFuncionamento.objects.all().order_by('dia_semana')
    dias_bloqueados = DiaBloqueado.objects.all().order_by('data')
    
    context = {
        'horarios': horarios,
        'dias_bloqueados': dias_bloqueados,
    }
    return render(request, 'site/admin_horarios.html', context)


def admin_relatorios(request):
    """Relatórios"""
    from datetime import date, timedelta
    from django.db.models import Count, Sum
    
    hoje = date.today()
    
    # Período
    periodo = request.GET.get('periodo', 'dia')
    
    if periodo == 'dia':
        data_inicio = hoje
        data_fim = hoje
    elif periodo == 'semana':
        data_inicio = hoje - timedelta(days=7)
        data_fim = hoje
    elif periodo == 'mes':
        data_inicio = date(hoje.year, hoje.month, 1)
        data_fim = hoje
    else:
        data_inicio = hoje
        data_fim = hoje
    
    # Consulta agendamentos no período
    agendamentos = Agendamento.objects.filter(
        data__gte=data_inicio,
        data__lte=data_fim
    )
    
    total_agendamentos = agendamentos.count()
    total_servicos = agendamentos.values('servico').annotate(count=Count('id'))
    
    # Receita
    receita = 0
    for ag in agendamentos.filter(status='FINALIZADO'):
        receita += float(ag.servico.preco)
    
    # Avaliação média
    avaliacoes = agendamentos.filter(nota_avaliacao__isnull=False)
    nota_media = 0
    if avaliacoes.exists():
        nota_media = avaliacoes.aggregate(Avg('nota_avaliacao'))['nota_avaliacao__avg']
    
    # Serviços mais procurados
    servicos_mais = list(
        agendamentos.values('servico__nome')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    
    context = {
        'periodo': periodo,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'total_agendamentos': total_agendamentos,
        'receita': receita,
        'nota_media': nota_media,
        'servicos_mais': servicos_mais,
    }
    return render(request, 'site/admin_relatorios.html', context)

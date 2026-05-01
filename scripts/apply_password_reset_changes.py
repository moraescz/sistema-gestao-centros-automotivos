#!/usr/bin/env python3
"""
Script para aplicar as mudanças necessárias para implementar reset de senha customizado
que permite usar username ou email, incluindo suporte para superusers sem email.
"""

import os
import re

def update_forms_py():
    """Adiciona o CustomPasswordResetForm ao cadastros/forms.py"""
    forms_content = '''from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from .models import Cliente, Veiculo, OrdemServico, Peca, ItemOrdemServico, PecaUtilizada, ConfiguracoesGerais, ServicoUtilizado, AnexoOrdemServico
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.forms import PasswordResetForm
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.conf import settings


# --- DEFINIÇÕES GLOBAIS DE ESTILO PARA OS FORMULÁRIOS ---
INPUT_CLASSES = "w-full bg-gray-900 border border-gray-700 rounded-md p-2 text-white focus:ring-blue-500 focus:border-blue-500"
TEXTAREA_CLASSES = INPUT_CLASSES + " h-24"
CHECKBOX_CLASSES = "h-5 w-5 text-blue-600 bg-gray-800 border-gray-600 rounded focus:ring-blue-500"


# --- FORMULÁRIO BASE PARA APLICAR ESTILOS AUTOMATICAMENTE ---
class StyledModelForm(forms.ModelForm):
    """
    Um ModelForm base que aplica automaticamente as classes CSS do Tailwind
    a todos os campos do formulário.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': CHECKBOX_CLASSES})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': TEXTAREA_CLASSES})
            else: # Aplica a todos os outros inputs (text, select, number, etc.)
                field.widget.attrs.update({'class': INPUT_CLASSES})

# --- FORMULÁRIOS DO SISTEMA ---

class ClienteForm(StyledModelForm):
    class Meta:
        model = Cliente
        fields = ['nome', 'cpf', 'telefone', 'email', 'endereco', 'cidade', 'estado']

class VeiculoForm(StyledModelForm):
    ano = forms.CharField(
        label="Ano",
        validators=[
            RegexValidator(
                regex=r'^\d{4}$',
                message="Digite exatamente 4 números.",
                code='invalid_year'
            )
        ],
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'maxlength': '4',
            'inputmode': 'numeric',
            'title': 'Digite exatamente 4 números (ex: 2020)'
        })
    )

    class Meta:
        model = Veiculo
        fields = ['modelo', 'placa', 'ano', 'cor', 'cliente']

    def clean_ano(self):
        ano = self.cleaned_data.get('ano')
        return int(ano)


class PecaForm(forms.ModelForm):
    class Meta:
        model = Peca
        fields = ['nome', 'aplicacao', 'quantidade', 'valor_unitario', 'quantidade_minima', 'imagem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 text-white text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 p-2.5'}),
            'aplicacao': forms.TextInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 text-white text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 p-2.5'}),
            'quantidade': forms.NumberInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 text-white text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 p-2.5'}),
            'valor_unitario': forms.NumberInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 text-white text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 p-2.5'}),
            'quantidade_minima': forms.NumberInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 text-white text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 p-2.5'}),
            'imagem': forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer'}),
        }

class OrdemServicoForm(StyledModelForm):
    class Meta:
        model = OrdemServico
        fields = [
            'veiculo', 'descricao', 'quilometragem', 'nivel_combustivel',
            'oleo_motor', 'alinhamento', 'bateria', 'palheta_dianteira', 'palheta_traseira',
            'luz_seta_dianteira_esq', 'luz_seta_dianteira_dir',
            'luz_farol_baixo_esq', 'luz_farol_baixo_dir',
            'luz_farol_alto_esq', 'luz_farol_alto_dir',
            'luz_seta_traseira_esq', 'luz_seta_traseira_dir',
            'luz_freio_esq', 'luz_freio_dir',
            'luz_re_esq', 'luz_re_dir',
            'observacoes_avarias',
            'data_conclusao', 'finalizada'
        ]
        # Widget específico para o campo de data, para usar o seletor do navegador
        widgets = {
            'data_conclusao': forms.DateInput(attrs={'type': 'date'}),
        }


class ItemOrdemServicoForm(StyledModelForm):
    class Meta:
        model = ItemOrdemServico
        fields = ['peca', 'servico_descricao', 'quantidade', 'valor_unitario']

class PecaUtilizadaForm(StyledModelForm):
    class Meta:
        model = PecaUtilizada
        fields = ['peca', 'quantidade_utilizada']

# --- FORMULÁRIOS CUSTOMIZADOS PARA FUNCIONÁRIOS (USER) ---

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': INPUT_CLASSES})
        self.fields['username'].label = "Nome de Usuário"
        self.fields['first_name'].label = "Nome"
        self.fields['last_name'].label = "Sobrenome"
        self.fields['email'].label = "E-mail"
        self.fields['password1'].label = "Senha"
        self.fields['password2'].label = "Confirmação de Senha"

class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('password', None) # Remove o campo de senha
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': CHECKBOX_CLASSES})
            else:
                field.widget.attrs.update({'class': INPUT_CLASSES})
        self.fields['username'].label = "Nome de Usuário"
        self.fields['first_name'].label = "Nome"
        self.fields['last_name'].label = "Sobrenome"
        self.fields['email'].label = "E-mail"
        self.fields['is_active'].label = "Ativo"

class ConfiguracoesGeraisForm(forms.ModelForm):
    """
    Formulário para o modelo ConfiguracoesGerais.
    Isso automatiza a validação, a renderização e o salvamento dos dados.
    """
    class Meta:
        model = ConfiguracoesGerais
        # Define quais campos do modelo serão exibidos no formulário
        fields = ['nome_empresa', 'logo', 'imagem_fundo']

        # Opcional: Personalize os widgets para melhor controle no template
        widgets = {
            'nome_empresa': forms.TextInput(attrs={'class': 'w-full bg-gray-900 bg-opacity-50 border border-gray-600 rounded-lg py-2 px-4 focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'logo': forms.FileInput(attrs={'class': 'hidden', 'id': 'logo_upload', 'accept': 'image/*', 'onchange': "previewImage(event, 'logo-preview', 'logo-preview-placeholder')"}),
            'imagem_fundo': forms.FileInput(attrs={'class': 'hidden', 'id': 'bg_upload', 'accept': 'image/*', 'onchange': "previewImage(event, 'bg-preview', 'bg-preview-placeholder')"})
        }

class PecaUtilizadaForm(forms.ModelForm):
    """
    Formulário para adicionar uma peça a uma Ordem de Serviço.
    """
    class Meta:
        model = PecaUtilizada
        fields = ['peca', 'quantidade_utilizada']
        widgets = {
            'peca': forms.Select(attrs={
                'class': 'w-full bg-gray-900 bg-opacity-50 border border-gray-700 rounded-lg py-2 px-4 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors'
            }),
            'quantidade_utilizada': forms.NumberInput(attrs={
                'class': 'w-full bg-gray-900 bg-opacity-50 border border-gray-700 rounded-lg py-2 px-4 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors',
                'min': '1'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra para mostrar apenas peças com estoque disponível.
        self.fields['peca'].queryset = Peca.objects.filter(quantidade__gt=0).order_by('nome')
        # Customiza como cada peça é exibida no dropdown.
        self.fields['peca'].label_from_instance = lambda obj: f"{obj.nome} (Estoque: {obj.quantidade})"

    def clean_quantidade_utilizada(self):
        quantidade = self.cleaned_data.get('quantidade_utilizada')
        peca = self.cleaned_data.get('peca')

        # Validação para garantir que a quantidade não exceda o estoque.
        if peca and quantidade and quantidade > peca.quantidade:
            raise forms.ValidationError(
                f"A quantidade utilizada ({quantidade}) não pode ser maior que a disponível em estoque ({peca.quantidade})."
            )
        if quantidade and quantidade < 1:
            raise forms.ValidationError("A quantidade deve ser de no mínimo 1.")

        return quantidade

class ServicoUtilizadoForm(forms.ModelForm):
    """
    Formulário para adicionar um serviço a uma Ordem de Serviço.
    """
    subtotal = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'w-full bg-gray-900 bg-opacity-50 border border-gray-700 rounded-lg py-2 px-4 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors',
            'readonly': 'readonly',
            'placeholder': 'Calculado automaticamente'
        }),
        label="Subtotal (R$)"
    )

    class Meta:
        model = ServicoUtilizado
        fields = ['descricao', 'quantidade', 'valor_unitario']
        widgets = {
            'descricao': forms.TextInput(attrs={
                'class': 'w-full bg-gray-900 bg-opacity-50 border border-gray-700 rounded-lg py-2 px-4 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors',
                'placeholder': 'Ex: Gasolina, Mão de obra, etc.'
            }),
            'quantidade': forms.NumberInput(attrs={
                'class': 'w-full bg-gray-900 bg-opacity-50 border border-gray-700 rounded-lg py-2 px-4 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors',
                'min': '1',
                'value': '1'
            }),
            'valor_unitario': forms.NumberInput(attrs={
                'class': 'w-full bg-gray-900 bg-opacity-50 border border-gray-700 rounded-lg py-2 px-4 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors',
                'min': '0.01',
                'step': '0.01',
                'required': 'required'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Calcular subtotal inicial se dados existem
        if self.instance and self.instance.pk:
            self.fields['subtotal'].initial = self.instance.valor
        elif self.data:
            quantidade = self.data.get('quantidade')
            valor_unitario = self.data.get('valor_unitario')
            if quantidade and valor_unitario:
                try:
                    self.fields['subtotal'].initial = float(quantidade) * float(valor_unitario)
                except (ValueError, TypeError):
                    pass

    def clean(self):
        cleaned_data = super().clean()
        quantidade = cleaned_data.get('quantidade')
        valor_unitario = cleaned_data.get('valor_unitario')

        if not quantidade or not valor_unitario:
            raise forms.ValidationError("Quantidade e valor unitário são obrigatórios.")

        # Calcular subtotal
        cleaned_data['valor'] = quantidade * valor_unitario
        cleaned_data['subtotal'] = cleaned_data['valor']

        return cleaned_data

class AnexoForm(forms.ModelForm):
    """
    Formulário para upload de anexos em Ordens de Serviço.
    """
    class Meta:
        model = AnexoOrdemServico
        fields = ['arquivo', 'descricao']
        widgets = {
            'arquivo': forms.FileInput(attrs={
                'class': 'w-full bg-gray-900 bg-opacity-50 border border-gray-700 rounded-lg py-2 px-4 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.txt'
            }),
            'descricao': forms.TextInput(attrs={
                'class': 'w-full bg-gray-900 bg-opacity-50 border border-gray-700 rounded-lg py-2 px-4 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors',
                'placeholder': 'Descrição opcional do anexo'
            }),
        }

class CustomPasswordResetForm(PasswordResetForm):
    """
    Formulário customizado para reset de senha que aceita username ou email.
    Permite reset de senha para superusers mesmo sem email definido.
    """
    email = forms.CharField(
        label="E-mail ou Nome de Usuário",
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'Digite seu e-mail ou nome de usuário'
        })
    )

    def clean_email(self):
        email_or_username = self.cleaned_data.get('email')
        if not email_or_username:
            raise ValidationError("Este campo é obrigatório.")

        # Busca usuário por email ou username (case-insensitive), apenas ativos
        try:
            user = User.objects.get(
                Q(email__iexact=email_or_username) | Q(username__iexact=email_or_username),
                is_active=True
            )
        except User.DoesNotExist:
            raise ValidationError("Usuário não encontrado.")

        # Para superusers sem email, usa o DEFAULT_FROM_EMAIL como fallback
        if user.is_superuser and not user.email:
            user.email = settings.DEFAULT_FROM_EMAIL

        # Armazena o usuário encontrado para uso posterior
        self.user = user
        return user.email

    def save(self, domain_override=None, subject_template_name=None,
             email_template_name=None, use_https=False, token_generator=None,
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        """
        Override do método save para usar o email do usuário encontrado.
        """
        # Usa o email do usuário encontrado (ou fallback para superuser)
        email = self.user.email
        self.cleaned_data['email'] = email

        # Chama o método save original com o email correto
        return super().save(
            domain_override=domain_override,
            subject_template_name=subject_template_name,
            email_template_name=email_template_name,
            use_https=use_https,
            token_generator=token_generator,
            from_email=from_email,
            request=request,
            html_email_template_name=html_email_template_name,
            extra_email_context=extra_email_context
        )'''

    with open('cadastros/forms.py', 'w', encoding='utf-8') as f:
        f.write(forms_content)
    print("✓ Atualizado cadastros/forms.py com CustomPasswordResetForm")

def update_urls_py():
    """Atualiza cadastros/urls.py para importar e usar o CustomPasswordResetForm"""
    urls_content = '''from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from cadastros import views
from cadastros.forms import CustomPasswordResetForm
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Autenticação, Home e Acesso Negado
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.home, name='home'),
    path('acesso-negado/', views.AcessoNegadoView.as_view(), name='acesso_negado'),

    # Clientes
    path('clientes/', views.listar_clientes, name='listar_clientes'),
    path('clientes/novo/', views.cadastrar_cliente, name='cadastrar_cliente'),
    path('clientes/detalhe/<int:pk>/', views.cliente_detalhe, name='cliente_detalhe'),
    path('clientes/editar/<int:pk>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/excluir/<int:pk>/', views.excluir_cliente, name='excluir_cliente'),
    
    # Veículos
    path('veiculos/', views.listar_veiculos, name='listar_veiculos'),
    path('veiculos/novo/', views.cadastrar_veiculo, name='cadastrar_veiculo'),
    path('veiculos/editar/<int:pk>/', views.editar_veiculo, name='editar_veiculo'),
    path('veiculos/excluir/<int:pk>/', views.excluir_veiculo, name='excluir_veiculo'),
    path('veiculos/historico/<int:pk>/', views.veiculo_historico, name='veiculo_historico'),

    # Peças e Estoque
    path('pecas/', views.listar_pecas, name='listar_pecas'),
    path('pecas/novo/', views.cadastrar_peca, name='cadastrar_peca'),
    path('pecas/editar/<int:pk>/', views.editar_peca, name='editar_peca'),
    path('pecas/excluir/<int:pk>/', views.excluir_peca, name='excluir_peca'),
    path('pecas/<int:pk>/remover-imagem/', views.remover_imagem_peca, name='remover_imagem_peca'), # <-- ROTA ADICIONADA AQUI

    # Ordens de Serviço (OS)
    path('os/', views.listar_ordens_servico, name='listar_ordens_servico'),
    path('os/novo/', views.cadastrar_ordem_servico, name='cadastrar_ordem_servico'),
    path('os/editar/<int:pk>/', views.editar_ordem_servico, name='editar_ordem_servico'),
    path('os/excluir/<int:pk>/', views.excluir_ordem_servico, name='excluir_ordem_servico'),
    path('os/pdf/<int:pk>/', views.gerar_os_pdf, name='gerar_os_pdf'),
    path('os/detalhe/<int:pk>/', views.ordem_servico_detalhe, name='ordem_servico_detalhe'),
    path('os/<int:ordem_id>/adicionar-peca/', views.adicionar_peca_na_os, name='adicionar_peca_na_os'),
    path('os/remover-peca/<int:pk>/', views.remover_peca_da_os, name='remover_peca_da_os'),
    path('os/<int:ordem_id>/adicionar-anexo/', views.adicionar_anexo_na_os, name='adicionar_anexo_na_os'),
    path('os/remover-anexo/<int:pk>/', views.remover_anexo_da_os, name='remover_anexo_da_os'),
    path('os/<int:ordem_id>/adicionar-servico/', views.adicionar_servico_na_os, name='adicionar_servico_na_os'),
    path('os/remover-servico/<int:pk>/', views.remover_servico_da_os, name='remover_servico_da_os'),

    # Funcionários e Permissões
    path('funcionarios/', views.listar_funcionarios, name='listar_funcionarios'),
    path('funcionarios/novo/', views.cadastrar_funcionario, name='cadastrar_funcionario'),
    path('funcionarios/editar/<int:pk>/', views.editar_funcionario, name='editar_funcionario'),
    path('funcionarios/excluir/<int:pk>/', views.excluir_funcionario, name='excluir_funcionario'),
    path('funcionarios/inativos/', views.listar_funcionarios_inativos, name='listar_funcionarios_inativos'),
    path('funcionarios/reativar/<int:pk>/', views.reativar_funcionario, name='reativar_funcionario'),
    path('privilegios/', views.gerenciar_privilegios, name='gerenciar_privilegios'),
    
    # Configurações do Sistema
    path('configuracoes/', views.configuracoes, name='configuracoes'),

    # ===== ROTA PARA O LOG DE ATIVIDADES =====
    path('logs/', views.listar_log_atividades, name='listar_log_atividades'),

    # Rotas de Redefinição de Senha
    path('reset_password/', auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html", form_class=CustomPasswordResetForm), name="password_reset"),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"), name="password_reset_confirm"),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"), name="password_reset_complete"),
]

# Configuração para servir ficheiros de mídia (logo, imagem de fundo) durante o desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)'''

    with open('cadastros/urls.py', 'w', encoding='utf-8') as f:
        f.write(urls_content)
    print("✓ Atualizado cadastros/urls.py com import e uso do CustomPasswordResetForm")

def update_password_reset_form_html():
    """Atualiza o template password_reset_form.html"""
    template_content = '''{% load static %}
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Redefinir Senha - {{ configuracoes.nome_empresa|default:"Centro Automotivo" }}</title>
    <link rel="icon" type="image/png" href="{% if configuracoes.logo and configuracoes.logo.url %}{{ configuracoes.logo.url }}{% else %}{% static 'images/logo.png' %}{% endif %}">
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Adiciona Font Awesome para os ícones -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        body { 
            font-family: 'Inter', sans-serif;
        }

        /* Define as cores primárias para consistência */
        :root {
            --cor-primaria: {{ configuracoes.cor_primaria|default:'#0d6efd' }};
            --cor-secundaria: {{ configuracoes.cor_secundaria|default:'#10B981' }};
        }

        /* --- Animações de Entrada --- */
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        /* --- Animação do Logo --- */
        @keyframes gentleFloat {
            0%, 100% {
                transform: translateY(0);
            }
            50% {
                transform: translateY(-8px);
            }
        }

        /* Aplica as animações */
        .login-card {
            animation: fadeInUp 0.6s ease-out forwards;
        }
        
        .logo-img {
            animation: gentleFloat 3s ease-in-out infinite, fadeInUp 0.5s ease-out forwards;
            animation-delay: 0s, 0.1s;
        }
        
        .form-field {
            opacity: 0;
            animation: fadeInUp 0.5s ease-out forwards;
        }

        /* --- Botão com Gradiente Animado --- */
        .btn-gradient {
            background: linear-gradient(90deg, var(--cor-secundaria) 0%, var(--cor-primaria) 100%);
            background-size: 200% auto;
            color: white;
            transition: background-position 0.4s ease-in-out, transform 0.2s ease;
        }

        .btn-gradient:hover {
            background-position: right center;
            transform: scale(1.03);
            filter: brightness(1.1);
        }

        /* --- Estilo de Foco dos Inputs --- */
        .form-input-styled {
            border-color: #374151;
            background-color: #1f2937; /* gray-800 */
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        
        .form-input-styled:focus {
            outline: none;
            border-color: var(--cor-primaria);
            box-shadow: 0 0 0 2px var(--cor-primaria);
        }

    </style>
</head>
<!-- Página fixa, sem scroll -->
<body class="bg-gray-900 h-screen overflow-hidden">

    <!-- Container principal com altura total -->
    <div class="relative h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-no-repeat bg-cover" style="background-image: url('{% if configuracoes.imagem_fundo and configuracoes.imagem_fundo.url %}{{ configuracoes.imagem_fundo.url }}{% else %}{% static 'images/fundo site tcc.png' %}{% endif %}');">
        <!-- Overlay escuro -->
        <div class="absolute bg-black opacity-60 inset-0 z-0"></div>
        
        <!-- Card -->
        <div class="login-card max-w-md w-full space-y-8 p-10 bg-gray-900 bg-opacity-80 rounded-2xl shadow-2xl z-10 border border-gray-700/50">
            <div>
                <img class="logo-img mx-auto h-24 w-auto rounded-full" src="{% if configuracoes.logo and configuracoes.logo.url %}{{ configuracoes.logo.url }}{% else %}{% static 'images/logo.png' %}{% endif %}" alt="Logo">
                <h2 class="mt-6 text-center text-3xl font-extrabold text-white" style="animation-delay: 0.2s;">
                    Esqueci Minha Senha
                </h2>
                <p class="mt-2 text-center text-sm text-gray-300 form-field" style="animation-delay: 0.3s;">
                    Informe seu e-mail ou nome de usuário e enviaremos um link para você criar uma nova senha.
                </p>
            </div>
            
            <form class="mt-8 space-y-6" method="POST">
                {% csrf_token %}
                
                <div class="space-y-4">
                    <!-- --- MELHORIA: Input de E-mail com Ícone --- -->
                    <div class="relative form-field" style="animation-delay: 0.4s;">
                        <span class="absolute inset-y-0 left-0 flex items-center pl-3">
                            <i class="fas fa-envelope text-gray-500"></i>
                        </span>
                        <input id="{{ form.email.id_for_label }}" name="{{ form.email.html_name }}" type="text" autocomplete="username" required 
                               class="form-input-styled relative block w-full pl-10 pr-3 py-3 border rounded-lg text-white placeholder-gray-500 sm:text-sm" 
                               placeholder="Digite seu e-mail ou nome de usuário">
                    </div>
                </div>

                <!-- --- MELHORIA: Mensagens de Erro Estilizadas --- -->
                {% if form.errors or form.non_field_errors %}
                    <div class="form-field bg-red-900/50 border border-red-700 text-red-300 px-4 py-3 rounded-lg relative" role="alert" style="animation-delay: 0.5s;">
                        <div class="flex">
                            <div class="py-1">
                                <i class="fas fa-exclamation-triangle mr-3"></i>
                            </div>
                            <div>
                                {% for field in form %}
                                    {% for error in field.errors %}
                                        <p class="text-sm">{{ error }}</p>
                                    {% endfor %}
                                {% endfor %}
                                {% for error in form.non_field_errors %}
                                    <p class="text-sm">{{ error }}</p>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                {% endif %}

                <div class="form-field" style="animation-delay: 0.5s;">
                    <!-- --- MELHORIA: Botão com Gradiente --- -->
                    <button type="submit" class="btn-gradient group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-blue-500">
                        <span class="absolute left-0 inset-y-0 flex items-center pl-3">
                            <i class="fas fa-paper-plane text-white/70"></i>
                        </span>
                        Enviar
                    </button>
                </div>

                <div class="text-sm text-center mt-4 form-field" style="animation-delay: 0.6s;">
                    <a href="{% url 'login' %}" class="font-medium text-blue-400 hover:text-blue-300 transition-colors">
                        <i class="fas fa-arrow-left mr-1"></i>
                        Voltar ao login
                    </a>
                </div>

            </form>
        </div>
    </div>

</body>
</html>'''

    with open('templates/registration/password_reset_form.html', 'w', encoding='utf-8') as f:
        f.write(template_content)
    print("✓ Atualizado templates/registration/password_reset_form.html")

def update_password_reset_email_html():
    """Atualiza o template password_reset_email.html"""
    email_content = '''Assunto: Redefinição de Senha

Olá {{ user.get_full_name|default:user.username }},

Você solicitou a redefinição de senha para sua conta ({{ user.username }}) no nosso sistema.

Clique no link abaixo para redefinir sua senha:

{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}

Se você não solicitou essa redefinição, ignore este e-mail.

Atenciosamente,
Equipe do Sistema'''

    with open('templates/registration/password_reset_email.html', 'w', encoding='utf-8') as f:
        f.write(email_content)
    print("✓ Atualizado templates/registration/password_reset_email.html")

def main():
    """Função principal que executa todas as atualizações"""
    print("Iniciando aplicação das mudanças para reset de senha customizado...")
    print()

    try:
        update_forms_py()
        update_urls_py()
        update_password_reset_form_html()
        update_password_reset_email_html()

        print()
        print("✅ Todas as mudanças foram aplicadas com sucesso!")
        print()
        print("Resumo das alterações:")
        print("- Adicionado CustomPasswordResetForm em cadastros/forms.py")
        print("- Atualizado cadastros/urls.py para usar o formulário customizado")
        print("- Modificado template password_reset_form.html")
        print("- Personalizado template password_reset_email.html")
        print()
        print("Agora superusers podem fazer reset de senha usando username mesmo sem email definido.")

    except Exception as e:
        print(f"❌ Erro durante a aplicação das mudanças: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())

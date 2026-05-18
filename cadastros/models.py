# cadastros/models.py
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.db.models import Sum, F, DecimalField
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime

class Cliente(models.Model):
    ESTADOS_CHOICES = [
        ('AC', 'Acre'),
        ('AL', 'Alagoas'),
        ('AP', 'Amapá'),
        ('AM', 'Amazonas'),
        ('BA', 'Bahia'),
        ('CE', 'Ceará'),
        ('DF', 'Distrito Federal'),
        ('ES', 'Espírito Santo'),
        ('GO', 'Goiás'),
        ('MA', 'Maranhão'),
        ('MT', 'Mato Grosso'),
        ('MS', 'Mato Grosso do Sul'),
        ('MG', 'Minas Gerais'),
        ('PA', 'Pará'),
        ('PB', 'Paraíba'),
        ('PR', 'Paraná'),
        ('PE', 'Pernambuco'),
        ('PI', 'Piauí'),
        ('RJ', 'Rio de Janeiro'),
        ('RN', 'Rio Grande do Norte'),
        ('RS', 'Rio Grande do Sul'),
        ('RO', 'Rondônia'),
        ('RR', 'Roraima'),
        ('SC', 'Santa Catarina'),
        ('SP', 'São Paulo'),
        ('SE', 'Sergipe'),
        ('TO', 'Tocantins'),
    ]

    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=14, unique=True, blank=True, null=True)
    telefone = models.CharField(max_length=16)
    email = models.EmailField(blank=True, null=True)
    endereco = models.CharField(max_length=200, blank=True, null=True)
    cidade = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=2, choices=ESTADOS_CHOICES, blank=True, null=True)

    def __str__(self):
        return self.nome

    class Meta:
        default_permissions = ('view', 'add', 'change', 'delete')

class Veiculo(models.Model):
    modelo = models.CharField(max_length=50)
    placa = models.CharField(max_length=10, unique=True)
    ano = models.IntegerField(validators=[MinValueValidator(1000),MaxValueValidator(9999)])
    cor = models.CharField(max_length=50, blank=True, null=True, verbose_name="Cor")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='veiculos')

    def __str__(self):
        return f"{self.modelo} ({self.placa})"

    class Meta:
        default_permissions = ('view', 'add', 'change', 'delete')

class Peca(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome da Peça")
    aplicacao = models.CharField(
        max_length=200, 
        verbose_name="Aplicação/Carro", 
        help_text="Veículos ou aplicações compatíveis com a peça.", 
        blank=True, 
        null=True
    )
    quantidade = models.PositiveIntegerField(help_text="Quantidade atual em estoque.")
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Unitário (R$)")
    quantidade_minima = models.PositiveIntegerField(
        verbose_name="Estoque Mínimo",
        help_text="Quantidade mínima para acionar o alerta de estoque baixo."
    )
    imagem = models.ImageField(upload_to='pecas/', blank=True, null=True)
    # --- NOVO CAMPO ---
    alerta_email_enviado = models.BooleanField(default=False, verbose_name="Alerta de Estoque Baixo Enviado")

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        # Cria um atributo temporário para sinalizar à view se o e-mail deve ser enviado
        # Envia alerta sempre que a quantidade estiver abaixo ou igual ao mínimo
        self.deve_enviar_alerta = self.quantidade <= self.quantidade_minima

        # Mantém o flag alerta_email_enviado para indicar se já foi alertado alguma vez (opcional)
        if self.deve_enviar_alerta and not self.alerta_email_enviado:
            self.alerta_email_enviado = True
        elif not self.deve_enviar_alerta:
            self.alerta_email_enviado = False

        super().save(*args, **kwargs) # Salva as alterações no banco (incluindo alerta_email_enviado)

    def enviar_email_de_alerta_para_usuario(self, usuario):
        assunto = f'Relatório do Sistema: Estoque Baixo - {self.nome}'
        remetente = settings.DEFAULT_FROM_EMAIL

        destinatarios = []
        # Tenta usar o e-mail do usuário logado, senão usa o fallback
        if usuario and usuario.email:
             destinatarios.append(usuario.email)
        else:
             # Defina um e-mail padrão ou busque de configurações se o usuário não tiver e-mail
             destinatarios.append('lorenzo.r@aluno.senai.br') # Seu fallback

        context = {
            'peca': self,
            'data_hora_alerta': datetime.now() # Data/Hora atual para o template do e-mail
        }
        # Renderiza a mensagem a partir de um template de texto simples
        mensagem = render_to_string('emails/alerta_estoque_baixo.txt', context)

        try:
            print(f"Tentando enviar email de alerta (SÍNCRONO) para '{destinatarios[0]}' sobre '{self.nome}'...")
            send_mail(
                assunto,
                mensagem,
                remetente,
                destinatarios,
                fail_silently=False, # Gera erro se falhar
            )
            print(f"SUCESSO: Email de alerta para '{self.nome}' enviado.")
        except Exception as e:
            print(f"ERRO (SÍNCRONO): Falha ao enviar email de estoque baixo para '{self.nome}': {e}")
            # Considerar logar o erro 'e' de forma mais robusta
            # Não re-levanta a exceção para não quebrar a view que chamou
            pass # Continua a execução mesmo se o e-mail falhar

    class Meta:
        verbose_name = "Peça"
        verbose_name_plural = "Peças"
        default_permissions = ('view', 'add', 'change', 'delete')

class OrdemServico(models.Model):
    # --- CAMPOS PRINCIPAIS (JÁ EXISTENTES) ---
    veiculo = models.ForeignKey(Veiculo, on_delete=models.CASCADE, related_name='ordens_servico', verbose_name="Veículo")
    descricao = models.TextField(verbose_name="Descrição Geral do Serviço")
    data_abertura = models.DateField(default=timezone.now)
    data_conclusao = models.DateField(blank=True, null=True, verbose_name="Data de Conclusão")
    finalizada = models.BooleanField(default=False, verbose_name="Finalizada")
    
    # --- CAMPO ADICIONADO DO SEGUNDO ARQUIVO ---
    STATUS_APROVACAO_CHOICES = [
        ('AGUARDANDO', 'Aguardando'),
        ('APROVADO', 'Aprovado'),
        ('REPROVADO', 'Reprovado'),
        ('FINALIZADO', 'Finalizado'),
    ]
    status_aprovacao = models.CharField(
        max_length=20,
        choices=STATUS_APROVACAO_CHOICES,
        default='AGUARDANDO',
        verbose_name="Status de Aprovação"
    )
    # --- FIM DA ADIÇÃO ---

    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Valor Total (R$)")

    # --- NOVOS CAMPOS DO CHECKLIST ---
    
    # Cabeçalho
    quilometragem = models.PositiveIntegerField(blank=True, null=True, verbose_name="Quilometragem (km)")
    
    # Status Gerais
    STATUS_CHOICES = [('BOM', 'Bom'), ('REVISAR', 'Revisar/Trocar'), ('RUIM', 'Ruim')]
    
    oleo_motor = models.CharField(max_length=50, choices=STATUS_CHOICES, blank=True, null=True, verbose_name="Óleo do Motor")
    alinhamento = models.CharField(max_length=50, choices=STATUS_CHOICES, blank=True, null=True, verbose_name="Alinhamento e Balanceamento")
    
    COMBUSTIVEL_CHOICES = [('VAZIO', 'Vazio'), ('RESERVA', 'Reserva'), ('1/4', '1/4'), ('1/2', '1/2'), ('3/4', '3/4'), ('CHEIO', 'Cheio')]
    nivel_combustivel = models.CharField(max_length=10, choices=COMBUSTIVEL_CHOICES, blank=True, null=True, verbose_name="Nível de Combustível")
    
    # Itens de Inspeção
    bateria = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True, null=True, verbose_name="Bateria")
    palheta_dianteira = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True, null=True, verbose_name="Palhetas Dianteiras")
    palheta_traseira = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True, null=True, verbose_name="Palhetas Traseiras")
    
    # Luzes
    luz_seta_dianteira_esq = models.BooleanField(default=False, verbose_name="Seta Diant. Esq.")
    luz_seta_dianteira_dir = models.BooleanField(default=False, verbose_name="Seta Diant. Dir.")
    luz_farol_baixo_esq = models.BooleanField(default=False, verbose_name="Farol Baixo Esq.")
    luz_farol_baixo_dir = models.BooleanField(default=False, verbose_name="Farol Baixo Dir.")
    luz_farol_alto_esq = models.BooleanField(default=False, verbose_name="Farol Alto Esq.")
    luz_farol_alto_dir = models.BooleanField(default=False, verbose_name="Farol Alto Dir.")
    luz_seta_traseira_esq = models.BooleanField(default=False, verbose_name="Seta Tras. Esq.")
    luz_seta_traseira_dir = models.BooleanField(default=False, verbose_name="Seta Tras. Dir.")
    luz_freio_esq = models.BooleanField(default=False, verbose_name="Freio Esq.")
    luz_freio_dir = models.BooleanField(default=False, verbose_name="Freio Dir.")
    luz_re_esq = models.BooleanField(default=False, verbose_name="Ré Esq.")
    luz_re_dir = models.BooleanField(default=False, verbose_name="Ré Dir.")

    # Avarias e Finalização
    observacoes_avarias = models.TextField(blank=True, null=True, verbose_name="Observações de Avarias e Finalização (riscos, amassados, etc.)")

    @property
    def get_valor_total_real(self):
        # 1. Valor base da OS (se houver, como Mão de Obra)
        valor_servico_base = self.valor_total or Decimal(0)
        
        # 2. Total de Peças (calculado no banco de dados)
        total_pecas_data = self.pecas_utilizadas.aggregate(
            total=Sum(F('quantidade_utilizada') * F('peca__valor_unitario'), output_field=DecimalField())
        )
        total_pecas = total_pecas_data['total'] or Decimal(0)

        # 3. Total de Serviços Adicionais (calculado no banco de dados)
        total_servicos_data = self.servicos_utilizados.aggregate(
            total=Sum('valor', output_field=DecimalField())
        )
        total_servicos = total_servicos_data['total'] or Decimal(0)

        # 4. Soma tudo
        return valor_servico_base + total_pecas + total_servicos

    def get_luzes_fields(self):
        luzes = {}
        for field in self._meta.get_fields():
            if isinstance(field, models.BooleanField) and field.name.startswith('luz_'):
                luzes[field.name] = field.verbose_name
        return luzes

    def get_luzes_ok(self):
        luzes_ok = []
        for field_name in self.get_luzes_fields().keys():
            if getattr(self, field_name):
                luzes_ok.append(field_name)
        return luzes_ok

    def __str__(self):
        return f"OS #{self.pk} - {self.veiculo.modelo} ({self.veiculo.placa})"

    class Meta:
        verbose_name = "Ordem de Serviço"
        verbose_name_plural = "Ordens de Serviço"
        default_permissions = ('view', 'add', 'change', 'delete')

class ItemOrdemServico(models.Model):
    ordem_servico = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name='itens')
    peca = models.ForeignKey('Peca', on_delete=models.SET_NULL, null=True, blank=True)
    servico_descricao = models.CharField(max_length=255, blank=True, null=True)
    quantidade = models.PositiveIntegerField(default=1)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Item {self.pk} - OS {self.ordem_servico.pk}"

    def get_valor_total(self):
        return self.quantidade * self.valor_unitario

    class Meta:
        default_permissions = ('view', 'add', 'change', 'delete')

class PecaUtilizada(models.Model):
    """
    Representa a relação entre uma Ordem de Serviço e uma Peça,
    incluindo a quantidade utilizada.
    """
    ordem_servico = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name='pecas_utilizadas')
    peca = models.ForeignKey(Peca, on_delete=models.PROTECT, help_text="Peça do estoque a ser utilizada.")
    quantidade_utilizada = models.PositiveIntegerField(help_text="Quantidade da peça utilizada no serviço.")

    class Meta:
        verbose_name = "Peça Utilizada"
        verbose_name_plural = "Peças Utilizadas"
        default_permissions = ('view', 'add', 'change', 'delete')
        unique_together = ('ordem_servico', 'peca')
        
    @property
    def subtotal(self):
        return self.quantidade_utilizada * self.peca.valor_unitario
        
    def __str__(self):
        return f"{self.quantidade_utilizada} x {self.peca.nome} na OS #{self.ordem_servico.pk}"

class ServicoUtilizado(models.Model):
    ordem_servico = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name='servicos_utilizados')
    descricao = models.CharField(max_length=255, help_text="Descrição do serviço ou custo adicional.")
    quantidade = models.PositiveIntegerField(default=1, help_text="Quantidade do serviço.")
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Valor unitário do serviço (opcional).")
    valor = models.DecimalField(max_digits=10, decimal_places=2, help_text="Valor total do serviço (calculado automaticamente se quantidade e valor_unitario forem informados).")

    class Meta:
        verbose_name = "Serviço Utilizado"
        verbose_name_plural = "Serviços Utilizados"
        default_permissions = ('view', 'add', 'change', 'delete')

    def save(self, *args, **kwargs):
        if self.quantidade and self.valor_unitario:
            self.valor = self.quantidade * self.valor_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.descricao} - R$ {self.valor} na OS #{self.ordem_servico.pk}"

class AnexoOrdemServico(models.Model):
    ordem_servico = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField(upload_to='anexos_os/', verbose_name="Arquivo")
    descricao = models.CharField(max_length=255, blank=True, null=True, verbose_name="Descrição")
    data_upload = models.DateTimeField(auto_now_add=True, verbose_name="Data de Upload")

    def __str__(self):
        return f"Anexo {self.pk} - {self.descricao or 'Sem descrição'}"

    class Meta:
        verbose_name = "Anexo da Ordem de Serviço"
        verbose_name_plural = "Anexos das Ordens de Serviço"
        default_permissions = ('view', 'add', 'change', 'delete')

class ConfiguracoesGerais(models.Model):
    nome_empresa = models.CharField(max_length=100, default="Centro Automotivo")
    logo = models.ImageField(upload_to='configuracoes/', blank=True, null=True, help_text="Logo da empresa (usado na barra lateral e ícone da aba).")
    imagem_fundo = models.ImageField(upload_to='configuracoes/', blank=True, null=True, help_text="Imagem de fundo do sistema.")
    telefone = models.CharField(max_length=25, blank=True, null=True, help_text="Telefone de contato da empresa.")
    endereco = models.TextField(blank=True, null=True, help_text="Endereço completo da empresa.")
    
    cor_primaria = models.CharField(
        max_length=7, 
        default='#0d6efd', 
        help_text="Cor principal do sistema (botões, links, sidebar ativa)."
    )
    cor_secundaria = models.CharField(
        max_length=7, 
        default='#10B981', 
        help_text="Cor secundária/destaque (gradientes, hover da sidebar)."
    )

    def __str__(self):
        return self.nome_empresa or "Configurações Gerais"

    class Meta:
        verbose_name = "Configuração Geral"
        verbose_name_plural = "Configurações Gerais"
        default_permissions = ('view', 'add', 'change', 'delete')
        permissions = [
            ("view_dashboard", "Pode visualizar o dashboard"),
        ]

    def save(self, *args, **kwargs):
        self.pk = 1
        super(ConfiguracoesGerais, self).save(*args, **kwargs)

    @classmethod
    def carregar(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

class LogAtividade(models.Model):
    """
    Modelo para registar as atividades dos utilizadores no sistema.
    """
    # Ações possíveis
    ACAO_CHOICES = [
        ('CRIAÇÃO', 'Criação'),
        ('ATUALIZAÇÃO', 'Atualização'),
        ('EXCLUSÃO', 'Exclusão'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='atividades')
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    detalhes = models.TextField(help_text="Descrição detalhada da ação realizada.")
    data_hora = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-data_hora']

    def __str__(self):
        return f"{self.usuario.username if self.usuario else 'Sistema'} - {self.acao} em {self.data_hora.strftime('%d/%m/%Y %H:%M')}"

class Funcionario(models.Model):
    """
    Modelo de perfil para funcionários, ligado ao User padrão do Django.
    """
    ESTADOS_CHOICES = [
        ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
        ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'),
        ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
        ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'),
        ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
        ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'),
        ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins'),
    ]

    # Link para o usuário de autenticação do Django
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_funcionario')

    # Campos do perfil (baseado nos seus testes)
    nome = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=16)
    cep = models.CharField(max_length=10, blank=True, null=True)
    rua = models.CharField(max_length=200, blank=True, null=True)
    estado = models.CharField(max_length=2, choices=ESTADOS_CHOICES, blank=True, null=True)
    
    # Adicione outros campos se necessário (ex: cargo, data_admissao, etc.)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"
        default_permissions = ('view', 'add', 'change', 'delete')


# ==================== NOVOS MODELOS PARA AGENDAMENTO ====================

class Servico(models.Model):
    """Serviços oferecidos pelo centro de estética automotiva"""
    nome = models.CharField(max_length=100, verbose_name="Nome do Serviço")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    preco = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço (R$)")
    duracao_minutos = models.PositiveIntegerField(verbose_name="Duração (minutos)")
    imagem = models.ImageField(upload_to='servicos/', blank=True, null=True, verbose_name="Imagem")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem de exibição")
    
    def __str__(self):
        return f"{self.nome} - R$ {self.preco}"

    class Meta:
        verbose_name = "Serviço"
        verbose_name_plural = "Serviços"
        ordering = ['ordem', 'nome']


class Agendamento(models.Model):
    """Agendamento de serviços"""
    STATUS_CHOICES = [
        ('AGENDADO', 'Agendado'),
        ('CONFIRMADO', 'Confirmado'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name='agendamentos', verbose_name="Serviço")
    cliente_nome = models.CharField(max_length=100, verbose_name="Nome do Cliente")
    cliente_telefone = models.CharField(max_length=16, verbose_name="Telefone (WhatsApp)")
    cliente_email = models.EmailField(blank=True, null=True, verbose_name="E-mail")
    data = models.DateField(verbose_name="Data")
    horario = models.TimeField(verbose_name="Horário")
    obs = models.TextField(blank=True, null=True, verbose_name="Observações")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AGENDADO', verbose_name="Status")
    
    # Avaliação
    nota_avaliacao = models.PositiveIntegerField(blank=True, null=True, verbose_name="Nota (1-5)")
    comentario_avaliacao = models.TextField(blank=True, null=True, verbose_name="Comentário da Avaliação")
    
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    @property
    def duracao(self):
        return self.servico.duracao_minutos
    
    def __str__(self):
        return f"{self.cliente_nome} - {self.servico.nome} ({self.data} às {self.horario})"

    class Meta:
        verbose_name = "Agendamento"
        verbose_name_plural = "Agendamentos"
        ordering = ['data', 'horario']


class HorarioFuncionamento(models.Model):
    """Horário de funcionamento semanal"""
    DIAS_SEMANA = [
        (0, 'Segunda-feira'),
        (1, 'Terça-feira'),
        (2, 'Quarta-feira'),
        (3, 'Quinta-feira'),
        (4, 'Sexta-feira'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    dia_semana = models.IntegerField(choices=DIAS_SEMANA, unique=True, verbose_name="Dia da Semana")
    hora_inicio = models.TimeField(verbose_name="Hora de Início")
    hora_fim = models.TimeField(verbose_name="Hora de Fim")
    intervalo_minutos = models.PositiveIntegerField(default=30, verbose_name="Intervalo entre atendimentos")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    
    def __str__(self):
        return f"{self.get_dia_semana_display()}: {self.hora_inicio} às {self.hora_fim}"
    
    @property
    def horarios_disponiveis(self):
        """Retorna lista de horários disponíveis"""
        from datetime import timedelta
        import datetime
        
        horarios = []
        atual = datetime.datetime.combine(datetime.date.today(), self.hora_inicio)
        fim = datetime.datetime.combine(datetime.date.today(), self.hora_fim)
        
        while atual < fim:
            horarios.append(atual.time())
            atual += timedelta(minutes=self.intervalo_minutos)
        
        return horarios

    class Meta:
        verbose_name = "Horário de Funcionamento"
        verbose_name_plural = "Horários de Funcionamento"
        ordering = ['dia_semana']


class DiaBloqueado(models.Model):
    """Dias bloqueados (feriados, férias, etc.)"""
    data = models.DateField(unique=True, verbose_name="Data Bloqueada")
    motivo = models.CharField(max_length=200, blank=True, null=True, verbose_name="Motivo")
    
    def __str__(self):
        return f"{self.data} - {self.motivo or 'Bloqueado'}"

    class Meta:
        verbose_name = "Dia Bloqueado"
        verbose_name_plural = "Dias Bloqueados"


class ConfiguracaoSite(models.Model):
    """Configurações do site público"""
    nome_empresa = models.CharField(max_length=100, default="Centro Estética Automotiva")
    telefone_whatsapp = models.CharField(max_length=16, help_text="Telefone com DDD para WhatsApp")
    logo = models.ImageField(upload_to='configuracoes/', blank=True, null=True, verbose_name="Logo")
    imagem_fundo = models.ImageField(upload_to='configuracoes/', blank=True, null=True, verbose_name="Imagem de Fundo")
    
    # Cores do tema
    cor_fundo = models.CharField(max_length=7, default='#000000', verbose_name="Cor de Fundo")
    cor_primaria = models.CharField(max_length=7, default='#00BFFF', verbose_name="Cor Primária (Azul Água)")
    cor_contraste = models.CharField(max_length=7, default='#FFFFFF', verbose_name="Cor de Contraste")
    
    # Mensagem automática do WhatsApp
    mensagem_whatsapp = models.TextField(
        default="Quero agendar {servico} para {data} às {horario}",
        verbose_name="Mensagem do WhatsApp",
        help_text="Use {servico}, {data}, {horario}, {nome} como variáveis"
    )
    
    # Informações adicionais
    endereco = models.TextField(blank=True, null=True, verbose_name="Endereço")
    instagram = models.CharField(max_length=100, blank=True, null=True, verbose_name="Instagram")
    facebook = models.CharField(max_length=100, blank=True, null=True, verbose_name="Facebook")
    
    def __str__(self):
        return self.nome_empresa
    
    def save(self, *args, **kwargs):
        self.pk = 1
        super(ConfiguracaoSite, self).save(*args, **kwargs)
    
    @classmethod
    def carregar(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    class Meta:
        verbose_name = "Configuração do Site"
        verbose_name_plural = "Configurações do Site"


class FotoTrabalho(models.Model):
    """Fotos de trabalhos realizados"""
    imagem = models.ImageField(upload_to='fotos_trabalho/', verbose_name="Imagem")
    titulo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Título")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    data_upload = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.titulo or f"Foto #{self.pk}"

    class Meta:
        verbose_name = "Foto do Trabalho"
        verbose_name_plural = "Fotos dos Trabalhos"
        ordering = ['-data_upload']

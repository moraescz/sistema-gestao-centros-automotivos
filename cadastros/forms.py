from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, PasswordResetForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.conf import settings
from .models import Cliente, Veiculo, OrdemServico, Peca, ItemOrdemServico, PecaUtilizada, ConfiguracoesGerais, ServicoUtilizado, AnexoOrdemServico, Funcionario


def validar_cpf(cpf):
    """
    Valida se o CPF é válido usando o algoritmo de verificação.
    Remove caracteres não numéricos e verifica os dígitos verificadores.
    """
    # Remove caracteres não numéricos
    cpf = ''.join(filter(str.isdigit, cpf))

    # Verifica se tem 11 dígitos
    if len(cpf) != 11:
        raise ValidationError('CPF deve ter 11 dígitos.')

    # Verifica se todos os dígitos são iguais (CPF inválido)
    if cpf == cpf[0] * 11:
        raise ValidationError('CPF inválido.')

    # Calcula primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    if resto == 10:
        resto = 0
    if resto != int(cpf[9]):
        raise ValidationError('CPF inválido.')

    # Calcula segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    if resto == 10:
        resto = 0
    if resto != int(cpf[10]):
        raise ValidationError('CPF inválido.')

    return cpf


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

class ClienteForm(forms.ModelForm): # ou StyledModelForm
    cpf = forms.CharField(
        label="CPF",
        max_length=14,
        # validators=[validar_cpf], # Seu validador
        widget=forms.TextInput(attrs={
            # 'class': INPUT_CLASSES,
            'placeholder': '000.000.000-00'
        })
    )
    telefone = forms.CharField(
        label="Telefone",
        max_length=16,
        validators=[
            RegexValidator(
                regex=r'^\(\d{2}\)\s\d{4,5}-\d{4}$',
                message="Telefone deve estar no formato (XX) XXXXX-XXXX ou (XX) XXXX-XXXX.",
                code='invalid_telefone'
            )
        ],
        widget=forms.TextInput(attrs={
            # 'class': INPUT_CLASSES,
            'placeholder': '(11) 99999-9999'
        })
    )

    # =================================================================
    # CAMPO 'CIDADE' MODIFICADO
    # =================================================================
    # Sobrescrevemos o campo 'cidade' do modelo
    cidade = forms.CharField(
        label="Cidade",
        required=False, # Igual ao seu modelo (blank=True, null=True)
        widget=forms.Select(
            attrs={
                # 'class': INPUT_CLASSES # Usando suas classes de estilo
            },
            # Começa com uma opção padrão. O JS vai preencher o resto.
            choices=[("", "Selecione um Estado")], 
        )
    )

    class Meta:
        model = Cliente
        fields = ['nome', 'cpf', 'telefone', 'email', 'endereco', 'estado', 'cidade']

    # =================================================================
    # MÉTODO __INIT__ ADICIONADO
    # =================================================================
    def __init__(self, *args, **kwargs):
        """
        Garante que, ao editar um cliente, o <select> de cidade
        seja pré-populado com a cidade já salva.
        """
        super().__init__(*args, **kwargs)
        
        # Se for um formulário de edição (tem instância) e já tem uma cidade salva
        if self.instance.pk and self.instance.cidade:
            saved_city = self.instance.cidade
            
            # Adicionamos a cidade salva como a *única* opção inicial.
            # O JavaScript irá carregar o restante das cidades do estado
            # e re-selecionar esta, se for o caso.
            self.fields['cidade'].widget.choices = [
                (saved_city, saved_city)
            ]
            self.fields['cidade'].initial = saved_city

    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        if cpf:
            # Remove formatação para validação
            cpf_numerico = ''.join(filter(str.isdigit, cpf))
            validar_cpf(cpf_numerico)
            # Retorna formatado
            return f"{cpf_numerico[:3]}.{cpf_numerico[3:6]}.{cpf_numerico[6:9]}-{cpf_numerico[9:]}"
        return cpf

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

class OrdemServicoForm(forms.ModelForm):
    
    # 1. CONFIGURAÇÃO DA DATA (Crucial para o navegador e validação)
    data_abertura = forms.DateField(
        label="Data de Abertura",
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date'} # A classe CSS será injetada automaticamente no __init__
        ),
        input_formats=['%Y-%m-%d', '%d/%m/%Y']
    )

    class Meta:
        model = OrdemServico
        fields = [
            'veiculo', 'quilometragem', 'descricao', 'nivel_combustivel',
            'oleo_motor', 'alinhamento', 'bateria', 'palheta_dianteira', 'palheta_traseira',
            'luz_seta_dianteira_esq', 'luz_seta_dianteira_dir',
            'luz_farol_baixo_esq', 'luz_farol_baixo_dir',
            'luz_farol_alto_esq', 'luz_farol_alto_dir',
            'luz_seta_traseira_esq', 'luz_seta_traseira_dir',
            'luz_freio_esq', 'luz_freio_dir',
            'luz_re_esq', 'luz_re_dir',
            'observacoes_avarias',
            'data_abertura'
        ]

        # 2. DEFINIÇÃO DOS TIPOS DE WIDGETS
        # Aqui definimos APENAS o comportamento funcional, não o estilo.
        widgets = {
            'veiculo': forms.Select(),            # Garante dropdown
            'nivel_combustivel': forms.Select(),  # Garante dropdown
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'observacoes_avarias': forms.Textarea(attrs={'rows': 3}),
            # Quilometragem é NumberInput por padrão do ModelForm (IntegerField), não precisa forçar aqui
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 3. ESTILIZAÇÃO CENTRALIZADA (CSS)
        
        # Estilo para Inputs de Texto, Selects, Datas e Números (Fundo escuro, borda cinza)
        style_input = (
            "bg-gray-800 border border-gray-700 text-white text-sm rounded-lg "
            "focus:ring-primary-500 focus:border-primary-500 block w-full p-2.5 "
            "placeholder-gray-400 color-scheme-dark"
        )

        # Estilo exclusivo para Checkboxes (Pequeno, quadrado)
        style_checkbox = (
            "w-5 h-5 text-primary-600 bg-gray-700 border-gray-600 rounded "
            "focus:ring-primary-500 focus:ring-2 cursor-pointer"
        )

        # 4. APLICAÇÃO AUTOMÁTICA
        for field_name, field in self.fields.items():
            # Verifica se o widget é um Checkbox (Checklist)
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = style_checkbox
            
            # Para todos os outros (Data, Texto, Select, Número, Textarea)
            else:
                field.widget.attrs['class'] = style_input

class ItemOrdemServicoForm(StyledModelForm):
    class Meta:
        model = ItemOrdemServico
        fields = ['peca', 'servico_descricao', 'quantidade', 'valor_unitario']

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
    
    # Se você quiser que o campo de cor seja um color picker no Django Admin:
    # cor_primaria = forms.CharField(widget=forms.TextInput(attrs={'type': 'color'}))
    # cor_secundaria = forms.CharField(widget=forms.TextInput(attrs={'type': 'color'}))
    
    class Meta:
        model = ConfiguracoesGerais
        fields = [
            'nome_empresa', 
            'logo', 
            'imagem_fundo', 
            'cor_primaria',
            'cor_secundaria',
        ]
        widgets = {
            # Você pode estilizar os campos de texto HEX aqui
            'cor_primaria': forms.TextInput(attrs={'class': 'seu-estilo-css'}),
            'cor_secundaria': forms.TextInput(attrs={'class': 'seu-estilo-css'}),
            # Exemplo:
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
    CORREÇÃO: Usa filter() e is_active=True para evitar MultipleObjectsReturned.
    """
    email = forms.CharField(
        label="E-mail ou Nome de Usuário",
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'Digite seu e-mail ou nome de usuário'
        })
    )
    
    # Adiciona um atributo para armazenar os usuários encontrados (QuerySet)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.users = User.objects.none() # Inicializa o QuerySet

    def clean_email(self):
        email_or_username = self.cleaned_data.get('email')
        if not email_or_username:
            raise ValidationError("Este campo é obrigatório.")

        # --- A CORREÇÃO PRINCIPAL ESTÁ AQUI: Usar filter() e buscar apenas usuários ATIVOS ---
        # O Q() busca por email OU username. A vírgula após o Q adiciona o filtro is_active=True (AND).
        self.users = User.objects.filter(
            Q(email__iexact=email_or_username) | Q(username__iexact=email_or_username),
            is_active=True # Garante que apenas usuários ativos sejam considerados
        )
        
        # O valor de retorno aqui não é usado para enviar o email, mas para a validação do formulário.
        # Retornamos o valor digitado. O método `save` da classe pai fará o trabalho.
        return email_or_username

    def get_users(self, email):
        """
        Sobrescreve o método interno da classe base para fornecer o QuerySet correto.
        Aplica a correção de email para superusers que não têm um (lógica do seu script original).
        """
        users_to_reset = list(self.users)
        
        # Aplica a correção de email para superusers sem email
        for user in users_to_reset:
            if user.is_superuser and not user.email:
                # Se for superuser sem email, usa o email de origem do sistema como fallback
                user.email = settings.DEFAULT_FROM_EMAIL
        
        # Retorna a lista de objetos User (que podem ter o email corrigido)
        return users_to_reset
        
    def save(self, *args, **kwargs):
        """
        Chama o save da classe base. 
        A lógica de envio de e-mail usará nosso método get_users customizado,
        enviando o e-mail apenas para o(s) usuário(s) ativo(s).
        """
        return super().save(*args, **kwargs)

class FuncionarioForm(forms.ModelForm):
    """
    Formulário para criar e editar o perfil de um Funcionário.
    """
    class Meta:
        model = Funcionario
        
        # Estes são os campos que aparecerão no formulário.
        # O campo 'user' é tratado separadamente na view.
        fields = [
            'nome', 
            'email', 
            'telefone', 
            'cep', 
            'rua', 
            'estado'
        ]
        
        # Adiciona as classes CSS do seu sistema aos campos
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-input-styled',
                'placeholder': 'Nome completo do funcionário'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input-styled',
                'placeholder': 'email@exemplo.com'
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-input-styled',
                'placeholder': '(00) 90000-0000'
            }),
            'cep': forms.TextInput(attrs={
                'class': 'form-input-styled',
                'placeholder': '00000-000'
            }),
            'rua': forms.TextInput(attrs={
                'class': 'form-input-styled',
                'placeholder': 'Rua, número e bairro'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-input-styled'
            }),
        }
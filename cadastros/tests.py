from django.test import TestCase
from django.contrib.auth.models import User
from .models import Funcionario  # 👈 CORRIGIDO
from .forms import FuncionarioForm  # 👈 CORRIGIDO

class FuncionarioTestCase(TestCase):  # 👈 CORRIGIDO
    
    def setUp(self):
        """Cria um User de autenticação que será usado pelos testes."""
        self.auth_user = User.objects.create_user(
            username='teste_user',
            password='password123',
            email='teste@email.com'
        )

    # Teste de criação direta
    def test_criar_funcionario(self): # 👈 CORRIGIDO
        """Testa a criação de um perfil 'Funcionario' ligado a um 'User'."""
        
        # Testa a criação do 'Funcionario' (Perfil) linkando ao 'User'
        funcionario_perfil = Funcionario.objects.create( # 👈 CORRIGIDO
            user=self.auth_user,  # <-- A LIGAÇÃO
            nome="Maria Silva",
            email="maria@email.com",
            telefone="1199999999",
            cep="01001000",
            rua="Rua Exemplo",
            estado="SP"
        )

        self.assertEqual(funcionario_perfil.nome, "Maria Silva")
        self.assertEqual(funcionario_perfil.user, self.auth_user)

    # Teste para validar se o formulário aceita dados válidos
    def test_formulario_dados_validos(self):
        """Testa se o formulário aceita dados válidos"""
        form_data = {
            'nome': 'João Silva',
            'email': 'joao@email.com',
            'telefone': '11999999999',
            'cep': '01001000',
            'rua': 'Rua das Flores',
            'estado': 'SP'
        }
        form = FuncionarioForm(data=form_data)  # 👈 CORRIGIDO
        self.assertTrue(form.is_valid())    

    # Teste para campos obrigatórios vazios
    def test_campos_obrigatorios_vazios(self):
        """Testa se campos obrigatórios não podem ficar vazios"""
        form_data = {
            'nome': '', 'email': '', 'telefone': '',
            'cep': '', 'rua': '', 'estado': ''
        }
        form = FuncionarioForm(data=form_data) # 👈 CORRIGIDO
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 6) # Assumindo que todos são obrigatórios
    
    # Teste específico para o campo nome obrigatório
    def test_nome_obrigatorio(self):
        """Testa especificamente se o campo nome é obrigatório"""
        form_data = {
            'nome': '',  # Campo nome vazio
            'email': 'teste@email.com',
            'telefone': '11999999999',
            'cep': '01001000',
            'rua': 'Rua Teste',
            'estado': 'SP'
        }
        form = FuncionarioForm(data=form_data) # 👈 CORRIGIDO
        self.assertFalse(form.is_valid())
        self.assertIn('nome', form.errors)
    
    # Teste específico para o campo email obrigatório
    def test_email_obrigatorio(self):
        form_data = {
            'nome': 'Teste Silva',
            'email': '',  # Campo email vazio
            'telefone': '11999999999',
            'cep': '01001000',
            'rua': 'Rua Teste',
            'estado': 'SP'
        }
        form = FuncionarioForm(data=form_data) # 👈 CORRIGIDO
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)      
    
    # Teste para validar formato de email
    def test_email_formato_valido(self):
        form_data = {
            'nome': 'Teste Silva',
            'email': 'email-invalido',  # Email sem formato válido
            'telefone': '11999999999',
            'cep': '01001000',
            'rua': 'Rua Teste',
            'estado': 'SP'
        }
        form = FuncionarioForm(data=form_data) # 👈 CORRIGIDO
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)      
    
    # Teste para garantir que o usuário é salvo corretamente no banco
    def test_funcionario_salvo(self): # 👈 CORRIGIDO
        """Testa se o funcionário é realmente salvo no banco após o cadastro"""
        funcionarios_antes = Funcionario.objects.count() # 👈 CORRIGIDO
        form_data = {
            'nome': 'Ana Costa',
            'email': 'ana@email.com',
            'telefone': '11988888888',
            'cep': '02002000',
            'rua': 'Avenida Principal',
            'estado': 'RJ'
        }
        form = FuncionarioForm(data=form_data) # 👈 CORRIGIDO
        
        self.assertTrue(form.is_valid(), f"Formulário inválido: {form.errors.as_json()}")
        
        # Simula como a view salvaria o formulário, linkando o user
        funcionario_perfil = form.save(commit=False) # 👈 CORRIGIDO
        funcionario_perfil.user = self.auth_user  # <-- A LIGAÇÃO
        funcionario_perfil.save()
        
        funcionarios_depois = Funcionario.objects.count() # 👈 CORRIGIDO
        self.assertEqual(funcionarios_depois, funcionarios_antes + 1)  

        funcionario_salvo = Funcionario.objects.get(email='ana@email.com') # 👈 CORRIGIDO
        self.assertEqual(funcionario_salvo.nome, 'Ana Costa')
        self.assertEqual(funcionario_salvo.telefone, '11988888888')
        self.assertEqual(funcionario_salvo.user, self.auth_user) # Verifica o link
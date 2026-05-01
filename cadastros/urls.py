from django.contrib import admin
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
    path('inicio/', views.roteador_inicial, name='roteador_inicial'),

    # Clientes
    path('clientes/', views.listar_clientes, name='listar_clientes'),
    path('clientes/novo/', views.cadastrar_cliente, name='cadastrar_cliente'),
    path('clientes/detalhe/<int:pk>/', views.cliente_detalhe, name='cliente_detalhe'),
    path('clientes/editar/<int:pk>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/excluir/<int:pk>/', views.excluir_cliente, name='excluir_cliente'),
    path('ajax/load-cities/', views.load_cities, name='ajax_load_cities'),
    
    # Veículos
    path('veiculos/', views.listar_veiculos, name='listar_veiculos'),
    path('veiculos/novo/', views.cadastrar_veiculo, name='cadastrar_veiculo'),
    path('veiculos/editar/<int:pk>/', views.editar_veiculo, name='editar_veiculo'),
    path('veiculos/excluir/<int:pk>/', views.excluir_veiculo, name='excluir_veiculo'),
    path('veiculos/historico/<int:pk>/', views.veiculo_historico, name='veiculo_historico'),

    # Peças e Estoque
    path('pecas/', views.listar_pecas, name='listar_pecas'),
    path('pecas/novo/', views.cadastrar_peca, name='cadastrar_peca'),
    path('pecas/detalhe/<int:pk>/', views.detalhar_peca, name='detalhar_peca'),
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
    path('os/finalizar/<int:pk>/', views.finalizar_ordem_servico, name='finalizar_ordem_servico'),
    path('os/alterar-status/<int:pk>/', views.alterar_status_aprovacao, name='alterar_status_aprovacao'),
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

    # ===== ROTAS PARA O LOG DE ATIVIDADES =====
    path('logs/', views.listar_log_atividades, name='listar_log_atividades'),
    path('logs/exportar/', views.exportar_logs_csv, name='exportar_logs_csv'),
    path('logs/importar/', views.importar_logs_csv, name='importar_logs_csv'),
    path('logs/importar-anexo/', views.importar_logs_anexo, name='importar_logs_anexo'),

    # Rotas de Redefinição de Senha (Mantida a versão do primeiro arquivo)
    path('reset_password/', auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html", form_class=CustomPasswordResetForm), name="password_reset"),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"), name="password_reset_confirm"),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"), name="password_reset_complete"),
]

# Configuração para servir ficheiros de mídia (logo, imagem de fundo) durante o desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
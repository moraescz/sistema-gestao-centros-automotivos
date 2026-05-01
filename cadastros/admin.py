from django.contrib import admin
from .models import (
    Cliente, Veiculo, Peca, OrdemServico, ItemOrdemServico,
    PecaUtilizada, ServicoUtilizado, AnexoOrdemServico,
    ConfiguracoesGerais, LogAtividade
)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf', 'telefone', 'email', 'cidade', 'estado')
    search_fields = ('nome', 'cpf', 'telefone', 'email')
    list_filter = ('estado', 'cidade')

@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ('modelo', 'placa', 'ano', 'cor', 'cliente')
    search_fields = ('modelo', 'placa', 'cliente__nome')
    list_filter = ('ano', 'cor')

@admin.register(Peca)
class PecaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'aplicacao', 'quantidade', 'valor_unitario', 'quantidade_minima')
    search_fields = ('nome', 'aplicacao')
    list_filter = ('quantidade_minima',)

@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = ('id', 'veiculo', 'data_abertura', 'data_conclusao', 'finalizada', 'valor_total')
    search_fields = ('veiculo__modelo', 'veiculo__placa', 'descricao')
    list_filter = ('finalizada', 'data_abertura', 'data_conclusao')
    readonly_fields = ('get_valor_total_real',)

@admin.register(ItemOrdemServico)
class ItemOrdemServicoAdmin(admin.ModelAdmin):
    list_display = ('ordem_servico', 'peca', 'servico_descricao', 'quantidade', 'valor_unitario')
    search_fields = ('ordem_servico__id', 'peca__nome', 'servico_descricao')
    list_filter = ('quantidade',)

@admin.register(PecaUtilizada)
class PecaUtilizadaAdmin(admin.ModelAdmin):
    list_display = ('ordem_servico', 'peca', 'quantidade_utilizada', 'subtotal')
    search_fields = ('ordem_servico__id', 'peca__nome')
    list_filter = ('quantidade_utilizada',)

@admin.register(ServicoUtilizado)
class ServicoUtilizadoAdmin(admin.ModelAdmin):
    list_display = ('ordem_servico', 'descricao', 'quantidade', 'valor_unitario', 'valor')
    search_fields = ('ordem_servico__id', 'descricao')
    list_filter = ('quantidade',)

@admin.register(AnexoOrdemServico)
class AnexoOrdemServicoAdmin(admin.ModelAdmin):
    list_display = ('ordem_servico', 'arquivo', 'descricao', 'data_upload')
    search_fields = ('ordem_servico__id', 'descricao')
    list_filter = ('data_upload',)

@admin.register(LogAtividade)
class LogAtividadeAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'acao', 'detalhes', 'data_hora')
    search_fields = ('usuario__username', 'acao', 'detalhes')
    list_filter = ('acao', 'data_hora')

@admin.register(ConfiguracoesGerais)
class ConfiguracoesGeraisAdmin(admin.ModelAdmin):
    """
    Configuração para o modelo ConfiguracoesGerais no painel de admin.
    """
    list_display = ('nome_empresa',)

    def has_add_permission(self, request):
        # Impede a criação de novos objetos, forçando o uso do Singleton.
        return not ConfiguracoesGerais.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Impede a exclusão do objeto Singleton.
        return False
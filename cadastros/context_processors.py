from .models import Peca
from django.db.models import F
from .models import ConfiguracoesGerais

def stock_alert(request):
    """
    Fornece um alerta global se houver peças com quantidade
    igual ou inferior ao estoque mínimo.
    """
    # Usamos F() para comparar o valor de dois campos do mesmo modelo diretamente no banco de dados.
    # Isso é mais eficiente do que iterar em Python.
    low_stock_pecas_count = Peca.objects.filter(quantidade__lte=F('quantidade_minima')).count()

    # Lista de todas as peças com estoque baixo, ordenadas por quantidade (mais baixa primeiro)
    low_stock_pecas = Peca.objects.filter(quantidade__lte=F('quantidade_minima')).order_by('quantidade')

    return {
        'low_stock_count': low_stock_pecas_count,
        'low_stock_pecas': low_stock_pecas,
    }

def configuracoes_globais(request):
    """
    Torna o objeto de configurações globais acessível em todos os templates.
    """
    return {'configuracoes': ConfiguracoesGerais.carregar()}
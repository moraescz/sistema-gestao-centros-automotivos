from .models import LogAtividade, ConfiguracoesGerais

def registrar_log(usuario, acao, objeto):
    """
    Cria e guarda um registo de log para uma ação específica.
    """
    detalhes = f"{acao.capitalize()} o objeto: {str(objeto)}"

    LogAtividade.objects.create(
        usuario=usuario,
        acao=acao.upper(),
        detalhes=detalhes
    )

def get_primary_color_classes():
    """
    Retorna um dicionário com classes CSS baseadas na cor primária das configurações gerais.
    """
    config = ConfiguracoesGerais.objects.first()
    if config and config.cor_primaria:
        primary_color = config.cor_primaria
        return {
            'bg_class': f'bg-primary',  # Usando classe padrão, pois a cor é customizada via CSS
            'text_class': f'text-primary',
            'primary_color': primary_color
        }
    else:
        return {
            'bg_class': 'bg-primary',
            'text_class': 'text-primary',
            'primary_color': '#0d6efd'
        }

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from .models import Peca, OrdemServico

@receiver(post_save, sender=Peca)
def alerta_estoque_baixo(sender, instance, **kwargs):
    if instance.quantidade <= instance.quantidade_minima:
        subject = f'Alerta de Estoque Baixo: {instance.nome}'
        html_message = render_to_string('emails/alerta_estoque_baixo.html', {'peca': instance})
        recipient_list = [settings.DEFAULT_FROM_EMAIL]  # Enviar para o admin; ajustar para lista de e-mails
        email = EmailMessage(subject, html_message, settings.DEFAULT_FROM_EMAIL, recipient_list)
        email.content_subtype = 'html'
        email.send()

@receiver(post_save, sender=OrdemServico)
def notificacao_os_finalizada(sender, instance, **kwargs):
    if instance.finalizada and instance.data_conclusao:
        subject = f'Ordem de Serviço Finalizada - OS #{instance.pk}'
        html_message = render_to_string('emails/os_finalizada.html', {'os': instance})
        recipient_list = [instance.veiculo.cliente.email] if instance.veiculo.cliente.email else []
        if recipient_list:
            email = EmailMessage(subject, html_message, settings.DEFAULT_FROM_EMAIL, recipient_list)
            email.content_subtype = 'html'
            email.send()

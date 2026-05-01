# Generated manually for adding codigo and aplicacao to Peca

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0011_delete_funcionario'),
    ]

    operations = [
        migrations.AddField(
            model_name='peca',
            name='aplicacao',
            field=models.CharField(default='', help_text='Veículos ou aplicações compatíveis com a peça.', max_length=200, verbose_name='Aplicação/Carro'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='peca',
            name='codigo',
            field=models.CharField(default='', help_text='Código único para identificação da peça.', max_length=50, verbose_name='Código da Peça'),
            preserve_default=False,
        ),
    ]

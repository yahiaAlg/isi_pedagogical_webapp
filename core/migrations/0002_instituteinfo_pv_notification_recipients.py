from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='instituteinfo',
            name='pv_notification_recipients',
            field=models.TextField(
                blank=True,
                verbose_name='Destinataires notification PV',
                help_text=(
                    "Adresses email qui recevront une notification à chaque génération "
                    "d'un PV de délibération (une adresse par ligne, ou séparées par des virgules)."
                ),
            ),
        ),
    ]

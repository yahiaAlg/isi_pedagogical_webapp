# Generated manually — adds the "active period" pin to SequenceCounter.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_alter_sequencecounter_kind'),
    ]

    operations = [
        migrations.AddField(
            model_name='sequencecounter',
            name='is_active',
            field=models.BooleanField(
                default=False,
                verbose_name='Période active',
                help_text=(
                    "Compteur utilisé pour attribuer le PROCHAIN numéro de ce type de "
                    "document. Un seul compteur peut être actif par type — l'activer "
                    "ici remplace le mois/l'année réel jusqu'à ce qu'un autre compteur "
                    "soit activé manuellement (contrôle manuel total, pas de retour "
                    "automatique)."
                ),
            ),
        ),
        migrations.AddConstraint(
            model_name='sequencecounter',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_active', True)),
                fields=('kind',),
                name='unique_sequence_kind_active',
            ),
        ),
    ]

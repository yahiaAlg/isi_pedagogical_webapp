from django.db import migrations, models

CHOICES = [
    ("default", "Par défaut"),
    ("fr", "Français uniquement"),
    ("ar", "Arabe uniquement"),
    ("both", "Français et arabe"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("formations", "0013_participant_verification_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="attestation_blocks",
            field=models.CharField(
                choices=CHOICES,
                default="default",
                help_text="Bloc(s) d'identité imprimé(s) sur les attestations de tous les participants de cette session. « Par défaut » : selon les noms saisis.",
                max_length=10,
                verbose_name="Blocs de l'attestation",
            ),
        ),
        migrations.AddField(
            model_name="participant",
            name="attestation_blocks",
            field=models.CharField(
                choices=CHOICES,
                default="default",
                help_text="Remplace le réglage de la session pour ce participant. « Par défaut » : hérite du réglage de la session.",
                max_length=10,
                verbose_name="Blocs de l'attestation",
            ),
        ),
    ]

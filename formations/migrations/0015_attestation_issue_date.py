from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("formations", "0014_attestation_blocks"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="attestation_issue_date",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Remplace la date « حرر ب سطيف في » imprimée sur les attestations de tous les participants de cette session. Vide : automatique (lendemain du dernier jour de la session).",
                verbose_name="Date « Fait à » de l'attestation",
            ),
        ),
        migrations.AddField(
            model_name="participant",
            name="attestation_issue_date",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Remplace la date de la session pour ce participant. Vide : hérite de la session (ou date automatique).",
                verbose_name="Date « Fait à » de l'attestation",
            ),
        ),
    ]

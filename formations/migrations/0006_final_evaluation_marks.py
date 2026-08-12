from django.db import migrations, models


def mark_existing_exam_scores_manual(apps, schema_editor):
    Participant = apps.get_model("formations", "Participant")
    Participant.objects.filter(exam_score__isnull=False).update(exam_score_manual=True)


class Migration(migrations.Migration):
    dependencies = [("formations", "0005_participant_qr_payload")]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="exam_score_manual",
            field=models.BooleanField(
                default=False,
                help_text="Lorsque faux, la note d'examen est calculée automatiquement à partir des notes théorique et pratique finales.",
                verbose_name="Note d'examen modifiée manuellement",
            ),
        ),
        migrations.AlterField(
            model_name="participant",
            name="score_theory",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name="Note théorique finale"),
        ),
        migrations.AlterField(
            model_name="participant",
            name="score_practice",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name="Note pratique finale"),
        ),
        migrations.RunPython(mark_existing_exam_scores_manual, migrations.RunPython.noop),
    ]

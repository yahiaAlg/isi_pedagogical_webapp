from django.db import migrations, models


def prefill_website_code(apps, schema_editor):
    Formation = apps.get_model("formations", "Formation")
    for f in Formation.objects.filter(website_code="").exclude(code=""):
        Formation.objects.filter(pk=f.pk).update(website_code=f.code)


class Migration(migrations.Migration):

    dependencies = [
        ("formations", "0011_alter_formation_title_ar"),
    ]

    operations = [
        migrations.AddField(
            model_name="formation",
            name="website_code",
            field=models.CharField(
                blank=True,
                help_text="Pré-rempli avec le code ; modifiez-le si le code du catalogue du site diffère (ex. MEE2512-2).",
                max_length=30,
                verbose_name="Code sur le site web",
            ),
        ),
        migrations.RunPython(prefill_website_code, migrations.RunPython.noop),
    ]

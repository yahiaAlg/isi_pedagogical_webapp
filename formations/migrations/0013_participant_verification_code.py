from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("formations", "0012_formation_website_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="verification_code",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=12,
                null=True,
                unique=True,
                verbose_name="Code de vérification",
            ),
        ),
    ]

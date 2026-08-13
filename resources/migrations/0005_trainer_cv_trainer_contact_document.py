import django.core.validators
from django.db import migrations, models

import resources.models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0004_assetmovement_total_price_assetmovement_unit_price_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainer',
            name='cv',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=resources.models.trainer_cv_path,
                validators=[django.core.validators.FileExtensionValidator(
                    allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'webp']
                )],
                verbose_name='CV',
                help_text='Image ou PDF.',
            ),
        ),
        migrations.AddField(
            model_name='trainer',
            name='contact_document',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=resources.models.trainer_contact_document_path,
                validators=[django.core.validators.FileExtensionValidator(
                    allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'webp']
                )],
                verbose_name='Document de contact',
                help_text='Image ou PDF.',
            ),
        ),
    ]

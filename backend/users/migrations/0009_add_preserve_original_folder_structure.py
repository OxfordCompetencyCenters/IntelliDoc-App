# Generated migration to add preserve_original_folder_structure field to IntelliDocProject

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_create_experiment_metric_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='intellidocproject',
            name='preserve_original_folder_structure',
            field=models.BooleanField(
                default=False,
                help_text='When enabled, preserves the original folder structure from uploaded files instead of auto-classifying into categories'
            ),
        ),
    ]

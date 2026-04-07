# Generated migration to add template_version field to IntelliDocProject

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_add_activity_tracker_page'),
    ]

    operations = [
        migrations.AddField(
            model_name='intellidocproject',
            name='template_version',
            field=models.CharField(blank=True, help_text='Template version at creation time', max_length=50),
        ),
    ]


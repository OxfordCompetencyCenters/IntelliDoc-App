# Manual migration: add per-document LLM folder organization mapping

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0012_project_document_summary'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectDocumentFolderOrganization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('folder_path', models.CharField(default='General', max_length=200)),
                ('llm_provider', models.CharField(default='openai', max_length=20)),
                ('llm_model', models.CharField(blank=True, max_length=100)),
                ('organization_method', models.CharField(default='llm_folder_org', max_length=50)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='folder_organization', to='users.projectdocument')),
            ],
            options={},
        ),
    ]


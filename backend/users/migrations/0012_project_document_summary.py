# Manual migration: add per-document summaries generated from provider File API

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0011_add_chatbot_page'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectDocumentSummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('long_summary', models.TextField(blank=True)),
                ('short_summary', models.TextField(blank=True)),
                ('llm_provider', models.CharField(default='openai', max_length=20)),
                ('llm_model', models.CharField(blank=True, max_length=100)),
                ('summarizer_used', models.CharField(default='file_api', max_length=50)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='document_summary', to='users.projectdocument')),
            ],
            options={
                'ordering': ['-generated_at'],
            },
        ),
    ]


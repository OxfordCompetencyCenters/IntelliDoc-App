# Generated manually for Full Document Mode feature
# To apply this migration, run in Docker container:
#   docker-compose exec backend python manage.py migrate users

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_add_preserve_original_folder_structure'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectdocument',
            name='llm_file_id_openai',
            field=models.CharField(
                blank=True, 
                help_text='OpenAI Files API file_id for this document', 
                max_length=255, 
                null=True
            ),
        ),
        migrations.AddField(
            model_name='projectdocument',
            name='llm_file_id_anthropic',
            field=models.CharField(
                blank=True, 
                help_text='Anthropic Files API file_id for this document', 
                max_length=255, 
                null=True
            ),
        ),
        migrations.AddField(
            model_name='projectdocument',
            name='llm_file_id_google',
            field=models.CharField(
                blank=True, 
                help_text='Google/Gemini Files API file URI for this document', 
                max_length=255, 
                null=True
            ),
        ),
        migrations.AddField(
            model_name='projectdocument',
            name='llm_file_uploaded_at',
            field=models.DateTimeField(
                blank=True, 
                help_text='When the document was uploaded to LLM providers', 
                null=True
            ),
        ),
    ]

# Generated manually for vector search toggle functionality

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('public_chatbot', '0002_add_system_prompt'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatbotconfiguration',
            name='enable_vector_search',
            field=models.BooleanField(default=True, help_text='Enable/disable ChromaDB vector search for context'),
        ),
    ]
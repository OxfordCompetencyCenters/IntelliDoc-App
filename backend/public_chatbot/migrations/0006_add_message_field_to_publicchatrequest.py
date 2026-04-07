# Generated migration to add message field for full message storage

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('public_chatbot', '0005_chatbotconfiguration_enable_query_rephrasing_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicchatrequest',
            name='message',
            field=models.TextField(blank=True, help_text='Full message content'),
        ),
    ]


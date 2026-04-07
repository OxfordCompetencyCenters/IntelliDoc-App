from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agent_orchestration', '0002_make_workflow_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowdeployment',
            name='initial_greeting',
            field=models.CharField(
                max_length=500,
                default='Hi! I am your AI assistant.',
                help_text='Initial greeting message shown by the embedded chatbot'
            ),
        ),
    ]



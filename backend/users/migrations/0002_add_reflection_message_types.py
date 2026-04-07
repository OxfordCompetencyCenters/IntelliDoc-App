# Generated manually to add reflection message types

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workflowexecutionmessage',
            name='message_type',
            field=models.CharField(
                choices=[
                    ('chat', 'Chat'),
                    ('workflow_start', 'Workflow Start'),
                    ('workflow_end', 'Workflow End'),
                    ('group_chat_summary', 'Group Chat Summary'),
                    ('system', 'System'),
                    ('error', 'Error'),
                    ('reflection_feedback', 'Reflection Feedback'),
                    ('reflection_revision', 'Reflection Revision'),
                    ('reflection_final', 'Reflection Final'),
                    ('reflection_iteration', 'Reflection Iteration'),
                ],
                default='chat',
                max_length=20
            ),
        ),
    ]
# Generated migration for adding human input tracking fields to DeploymentSession
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agent_orchestration', '0004_add_deployment_session_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='deploymentsession',
            name='awaiting_human_input',
            field=models.BooleanField(default=False, help_text='Whether this session is awaiting human input from UserProxyAgent'),
        ),
        migrations.AddField(
            model_name='deploymentsession',
            name='paused_execution_id',
            field=models.CharField(blank=True, help_text='WorkflowExecution ID of the paused execution', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='deploymentsession',
            name='human_input_prompt',
            field=models.TextField(blank=True, help_text='Last conversation message to display when requesting human input'),
        ),
        migrations.AddField(
            model_name='deploymentsession',
            name='human_input_agent_name',
            field=models.CharField(blank=True, help_text='Name of the UserProxyAgent awaiting input', max_length=200),
        ),
        migrations.AddField(
            model_name='deploymentsession',
            name='human_input_agent_id',
            field=models.CharField(blank=True, help_text='Node ID of the UserProxyAgent awaiting input', max_length=100),
        ),
    ]


# Generated migration for DeploymentSession and DeploymentExecution models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('agent_orchestration', '0003_add_initial_greeting'),
        ('users', '0001_initial'),  # Adjust if needed based on your users app migrations
    ]

    operations = [
        migrations.CreateModel(
            name='DeploymentSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(help_text='Unique session identifier from client', max_length=100)),
                ('conversation_history', models.JSONField(default=list, help_text='Full conversation history as list of messages: [{"role": "user|assistant", "content": "..."}, ...]')),
                ('message_count', models.IntegerField(default=0, help_text='Total number of messages in this session')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this session is currently active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_activity', models.DateTimeField(auto_now=True, help_text='Last time a message was added to this session')),
                ('deployment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='agent_orchestration.workflowdeployment')),
            ],
            options={
                'ordering': ['-last_activity'],
            },
        ),
        migrations.CreateModel(
            name='DeploymentExecution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('execution_id', models.CharField(help_text='Unique execution identifier', max_length=100, unique=True)),
                ('user_query', models.TextField(help_text='The user query that triggered this execution')),
                ('assistant_response', models.TextField(help_text='The assistant response from the workflow')),
                ('execution_time_ms', models.IntegerField(blank=True, help_text='Execution time in milliseconds', null=True)),
                ('status', models.CharField(choices=[('success', 'Success'), ('error', 'Error'), ('rate_limited', 'Rate Limited'), ('blocked', 'Blocked'), ('cors_denied', 'CORS Denied')], default='success', help_text='Execution status', max_length=20)),
                ('error_message', models.TextField(blank=True, help_text='Error message if execution failed', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('deployment_session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executions', to='agent_orchestration.deploymentsession')),
                ('workflow_execution', models.ForeignKey(blank=True, help_text='Reference to underlying WorkflowExecution record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deployment_executions', to='users.workflowexecution')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='deploymentsession',
            index=models.Index(fields=['deployment', 'session_id'], name='deploy_session_deploy_sess_idx'),
        ),
        migrations.AddIndex(
            model_name='deploymentsession',
            index=models.Index(fields=['deployment', 'last_activity'], name='deploy_session_deploy_act_idx'),
        ),
        migrations.AddIndex(
            model_name='deploymentsession',
            index=models.Index(fields=['is_active', 'last_activity'], name='deploy_session_active_act_idx'),
        ),
        migrations.AddConstraint(
            model_name='deploymentsession',
            constraint=models.UniqueConstraint(fields=['deployment', 'session_id'], name='unique_deployment_session'),
        ),
        migrations.AddIndex(
            model_name='deploymentexecution',
            index=models.Index(fields=['deployment_session', 'created_at'], name='deploy_exec_session_created_idx'),
        ),
        migrations.AddIndex(
            model_name='deploymentexecution',
            index=models.Index(fields=['execution_id'], name='deploy_exec_exec_id_idx'),
        ),
        migrations.AddIndex(
            model_name='deploymentexecution',
            index=models.Index(fields=['status'], name='deploy_exec_status_idx'),
        ),
    ]


# Generated migration for WorkflowDeployment models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0003_add_workflow_evaluation_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkflowDeployment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=False, help_text='Whether the deployment is currently active')),
                ('endpoint_path', models.CharField(editable=False, help_text='Auto-generated endpoint path', max_length=200)),
                ('rate_limit_per_minute', models.IntegerField(default=10, help_text='Default rate limit per minute for origins without specific limits')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_deployments', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workflow_deployments', to='users.intellidocproject')),
                ('workflow', models.ForeignKey(blank=True, help_text='The workflow being deployed', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='deployments', to='users.agentworkflow')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddIndex(
            model_name='workflowdeployment',
            index=models.Index(fields=['project', 'is_active'], name='agent_orch_project_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowdeployment',
            index=models.Index(fields=['is_active'], name='agent_orch_is_active_idx'),
        ),
        migrations.AddConstraint(
            model_name='workflowdeployment',
            constraint=models.UniqueConstraint(condition=models.Q(('is_active', True)), fields=('project',), name='unique_active_deployment_per_project'),
        ),
        migrations.CreateModel(
            name='WorkflowAllowedOrigin',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origin', models.CharField(help_text='Allowed origin (e.g., https://example.com)', max_length=500)),
                ('rate_limit_per_minute', models.IntegerField(default=10, help_text='Rate limit per minute for this specific origin')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this origin is currently allowed')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deployment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='allowed_origins', to='agent_orchestration.workflowdeployment')),
            ],
            options={
                'ordering': ['origin'],
                'unique_together': {('deployment', 'origin')},
            },
        ),
        migrations.AddIndex(
            model_name='workflowallowedorigin',
            index=models.Index(fields=['deployment', 'is_active'], name='agent_orch_deployment_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowallowedorigin',
            index=models.Index(fields=['origin'], name='agent_orch_origin_idx'),
        ),
        migrations.CreateModel(
            name='WorkflowDeploymentRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origin', models.CharField(help_text='Origin of the request', max_length=500)),
                ('request_id', models.CharField(help_text='Unique request identifier', max_length=100, unique=True)),
                ('session_id', models.CharField(blank=True, help_text='Optional session ID for conversation tracking', max_length=100, null=True)),
                ('message_preview', models.CharField(blank=True, help_text='Privacy-safe truncated message (first 100 chars)', max_length=100)),
                ('response_generated', models.BooleanField(default=False, help_text='Whether a response was successfully generated')),
                ('status', models.CharField(choices=[('success', 'Success'), ('error', 'Error'), ('rate_limited', 'Rate Limited'), ('blocked', 'Blocked'), ('cors_denied', 'CORS Denied')], default='success', max_length=20)),
                ('execution_time_ms', models.IntegerField(blank=True, help_text='Workflow execution time in milliseconds', null=True)),
                ('error_message', models.TextField(blank=True, help_text='Error message if request failed')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('deployment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requests', to='agent_orchestration.workflowdeployment')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='workflowdeploymentrequest',
            index=models.Index(fields=['deployment', 'created_at'], name='agent_orch_deployment_created_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowdeploymentrequest',
            index=models.Index(fields=['origin', 'created_at'], name='agent_orch_origin_created_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowdeploymentrequest',
            index=models.Index(fields=['status'], name='agent_orch_status_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowdeploymentrequest',
            index=models.Index(fields=['session_id', 'created_at'], name='agent_orch_session_created_idx'),
        ),
    ]


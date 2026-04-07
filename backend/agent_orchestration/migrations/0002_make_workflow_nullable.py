# Generated migration to make workflow field nullable

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('agent_orchestration', '0001_create_workflow_deployment_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workflowdeployment',
            name='workflow',
            field=models.ForeignKey(
                blank=True,
                help_text='The workflow being deployed',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='deployments',
                to='users.agentworkflow'
            ),
        ),
    ]


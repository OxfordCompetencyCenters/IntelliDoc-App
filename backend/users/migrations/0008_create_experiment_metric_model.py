# Generated migration to create ExperimentMetric model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_add_system_performance_analysis_page'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExperimentMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('experiment_type', models.CharField(help_text='Type of experiment: intelligent_delegation, workflow_execution, docaware_single, docaware_context', max_length=50)),
                ('metric_data', models.JSONField(default=dict, help_text='All metric values for this experiment (timing, counts, percentages, etc.)')),
                ('configuration', models.JSONField(default=dict, help_text='Experiment configuration (delegate count, threshold, agent count, RAG status, etc.)')),
                ('execution_id', models.CharField(blank=True, help_text='Optional: Link to WorkflowExecution if this metric is from a workflow execution', max_length=100)),
                ('evaluation_id', models.CharField(blank=True, help_text='Optional: Link to WorkflowEvaluation if this metric is from an evaluation', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='experiment_metrics', to='users.intellidocproject')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='experimentmetric',
            index=models.Index(fields=['project', 'experiment_type', '-created_at'], name='users_exper_project_exper_created_idx'),
        ),
        migrations.AddIndex(
            model_name='experimentmetric',
            index=models.Index(fields=['project', '-created_at'], name='users_exper_project_created_idx'),
        ),
        migrations.AddIndex(
            model_name='experimentmetric',
            index=models.Index(fields=['experiment_type', '-created_at'], name='users_exper_experiment_created_idx'),
        ),
    ]


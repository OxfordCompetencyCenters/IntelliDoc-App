# Generated migration for WorkflowEvaluation and WorkflowEvaluationResult models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0002_add_reflection_message_types'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkflowEvaluation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('evaluation_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('csv_filename', models.CharField(max_length=255)),
                ('total_rows', models.IntegerField()),
                ('completed_rows', models.IntegerField(default=0)),
                ('failed_rows', models.IntegerField(default=0)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('executed_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('workflow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluations', to='users.agentworkflow')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='workflowevaluation',
            index=models.Index(fields=['workflow', 'status'], name='users_workf_workflo_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowevaluation',
            index=models.Index(fields=['evaluation_id'], name='users_workf_evaluat_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowevaluation',
            index=models.Index(fields=['created_at'], name='users_workf_created_idx'),
        ),
        migrations.CreateModel(
            name='WorkflowEvaluationResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('row_number', models.IntegerField()),
                ('input_text', models.TextField()),
                ('expected_output', models.TextField()),
                ('workflow_output', models.TextField(blank=True, help_text='Aggregated End node input messages')),
                ('execution_id', models.CharField(blank=True, help_text='Reference to WorkflowExecution', max_length=100)),
                ('rouge_1_score', models.FloatField(blank=True, null=True)),
                ('rouge_2_score', models.FloatField(blank=True, null=True)),
                ('rouge_l_score', models.FloatField(blank=True, null=True)),
                ('bleu_score', models.FloatField(blank=True, null=True)),
                ('bert_score', models.FloatField(blank=True, null=True)),
                ('semantic_similarity', models.FloatField(blank=True, null=True)),
                ('average_score', models.FloatField(blank=True, null=True)),
                ('status', models.CharField(choices=[('success', 'Success'), ('failed', 'Failed'), ('pending', 'Pending')], default='pending', max_length=20)),
                ('error_message', models.TextField(blank=True)),
                ('execution_time_seconds', models.FloatField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('evaluation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='users.workflowevaluation')),
            ],
            options={
                'ordering': ['row_number'],
                'unique_together': {('evaluation', 'row_number')},
            },
        ),
        migrations.AddIndex(
            model_name='workflowevaluationresult',
            index=models.Index(fields=['evaluation', 'row_number'], name='users_workf_evaluat_row_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowevaluationresult',
            index=models.Index(fields=['evaluation', 'status'], name='users_workf_evaluat_sta_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowevaluationresult',
            index=models.Index(fields=['average_score'], name='users_workf_average_idx'),
        ),
    ]


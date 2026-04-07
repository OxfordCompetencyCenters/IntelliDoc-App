# Manual migration: add per-URL summaries for web search URL mode

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0015_sync_v2_navigation_pages'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebSearchUrlSummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(max_length=2000)),
                ('short_summary', models.TextField(blank=True)),
                ('long_summary', models.TextField(blank=True)),
                ('llm_provider', models.CharField(default='openai', max_length=20)),
                ('llm_model', models.CharField(blank=True, max_length=100)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='url_summaries',
                    to='users.intellidocproject',
                )),
            ],
            options={
                'ordering': ['url'],
                'unique_together': {('project', 'url')},
            },
        ),
    ]

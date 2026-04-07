# Migration to sync all AICC-IntelliDoc v2 projects with current template navigation pages

from django.db import migrations


# Canonical page definitions from the current aicc-intellidoc-v2 template
CANONICAL_PAGES = {
    1: {'name': 'Project Documents', 'short_name': 'Documents', 'icon': 'fa-home', 'description': 'Upload and manage documents', 'features': ['document_management', 'upload_interface', 'processing_status']},
    2: {'name': 'Agent Orchestration', 'short_name': 'Agents', 'icon': 'fa-sitemap', 'description': 'Design and run AI workflows', 'features': ['visual_workflow_designer', 'agent_management', 'real_time_execution', 'workflow_history']},
    3: {'name': 'Evaluation', 'short_name': 'Evaluation', 'icon': 'fa-clipboard-check', 'description': 'Test and compare results', 'features': ['workflow_evaluation', 'csv_upload', 'metrics_comparison', 'batch_testing']},
    4: {'name': 'Deploy', 'short_name': 'Deploy', 'icon': 'fa-rocket', 'description': 'Publish your workflow endpoint', 'features': ['workflow_deployment', 'public_endpoint', 'origin_management', 'rate_limiting']},
    5: {'name': 'Activity Tracker', 'short_name': 'Activity', 'icon': 'fa-chart-line', 'description': 'Monitor sessions and usage', 'features': ['deployment_activity', 'session_tracking', 'analytics']},
    6: {'name': 'System Performance Analysis', 'short_name': 'Performance', 'icon': 'fa-chart-bar', 'description': 'Review experiment metrics', 'features': ['experiment_metrics', 'performance_analysis', 'system_evaluation']},
    7: {'name': 'Chatbot', 'short_name': 'Chatbot', 'icon': 'fa-comments', 'description': 'Chat with your assistant', 'features': ['in_app_chatbot']},
}


def sync_v2_navigation_pages(apps, schema_editor):
    """Sync all v2 project navigation pages with the current template definition."""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')

    updated_count = 0
    for project in IntelliDocProject.objects.filter(template_type='aicc-intellidoc-v2'):
        if not project.navigation_pages:
            continue

        changed = False
        for page in project.navigation_pages:
            page_num = page.get('page_number')
            canonical = CANONICAL_PAGES.get(page_num)
            if not canonical:
                continue

            # Update all fields to match canonical definition
            for key in ('name', 'short_name', 'icon', 'description', 'features'):
                if page.get(key) != canonical[key]:
                    page[key] = canonical[key]
                    changed = True

        # Backfill template_version if blank
        if not project.template_version:
            project.template_version = '2.0.0'
            changed = True

        if changed:
            project.save(update_fields=['navigation_pages', 'template_version'])
            updated_count += 1

    print(f"✅ Synced navigation pages for {updated_count} v2 projects")


def reverse_sync(apps, schema_editor):
    """Reverse: remove description field from navigation pages."""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')

    updated_count = 0
    for project in IntelliDocProject.objects.filter(template_type='aicc-intellidoc-v2'):
        if not project.navigation_pages:
            continue

        changed = False
        for page in project.navigation_pages:
            if 'description' in page:
                del page['description']
                changed = True

        if changed:
            project.save(update_fields=['navigation_pages'])
            updated_count += 1

    print(f"✅ Removed description from {updated_count} v2 projects")


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0014_add_memory_and_citation_to_summary'),
    ]

    operations = [
        migrations.RunPython(
            sync_v2_navigation_pages,
            reverse_sync,
        ),
    ]

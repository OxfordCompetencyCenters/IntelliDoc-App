# Generated migration to rename Overview to Project Documents in existing projects

from django.db import migrations


def update_navigation_pages(apps, schema_editor):
    """Update all existing projects' navigation_pages to rename Overview to Project Documents"""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')
    
    updated_count = 0
    for project in IntelliDocProject.objects.all():
        if project.navigation_pages:
            updated = False
            for page in project.navigation_pages:
                if page.get('name') == 'Overview':
                    page['name'] = 'Project Documents'
                    page['short_name'] = 'Documents'
                    updated = True
                    updated_count += 1
                    break  # Only update first occurrence (page_number 1)
            if updated:
                project.save(update_fields=['navigation_pages'])
    
    print(f"✅ Updated {updated_count} projects with 'Overview' renamed to 'Project Documents'")


def reverse_update_navigation_pages(apps, schema_editor):
    """Reverse migration: rename Project Documents back to Overview"""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')
    
    updated_count = 0
    for project in IntelliDocProject.objects.all():
        if project.navigation_pages:
            updated = False
            for page in project.navigation_pages:
                if page.get('name') == 'Project Documents':
                    page['name'] = 'Overview'
                    page['short_name'] = 'Overview'
                    updated = True
                    updated_count += 1
                    break
            if updated:
                project.save(update_fields=['navigation_pages'])
    
    print(f"✅ Reverted {updated_count} projects back to 'Overview'")


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_add_workflow_evaluation_models'),
    ]

    operations = [
        migrations.RunPython(update_navigation_pages, reverse_update_navigation_pages),
    ]


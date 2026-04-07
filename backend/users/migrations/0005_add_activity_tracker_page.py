# Generated migration to add Activity Tracker page to existing projects

from django.db import migrations


def add_activity_tracker_page(apps, schema_editor):
    """Add Activity Tracker as 5th navigation page to existing projects"""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')
    
    activity_tracker_page = {
        'page_number': 5,
        'name': 'Activity Tracker',
        'short_name': 'Activity',
        'icon': 'fa-chart-line',
        'features': ['deployment_activity', 'session_tracking', 'analytics']
    }
    
    updated_count = 0
    for project in IntelliDocProject.objects.all():
        if project.navigation_pages:
            # Check if Activity Tracker page already exists
            has_activity_tracker = any(
                page.get('name') == 'Activity Tracker' or page.get('page_number') == 5
                for page in project.navigation_pages
            )
            
            if not has_activity_tracker:
                # Add Activity Tracker page
                project.navigation_pages.append(activity_tracker_page)
                project.total_pages = max(project.total_pages or 4, 5)
                project.save(update_fields=['navigation_pages', 'total_pages'])
                updated_count += 1
    
    print(f"✅ Added Activity Tracker page to {updated_count} projects")


def reverse_add_activity_tracker_page(apps, schema_editor):
    """Reverse migration: remove Activity Tracker page from projects"""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')
    
    updated_count = 0
    for project in IntelliDocProject.objects.all():
        if project.navigation_pages:
            # Remove Activity Tracker page
            original_length = len(project.navigation_pages)
            project.navigation_pages = [
                page for page in project.navigation_pages
                if page.get('name') != 'Activity Tracker' and page.get('page_number') != 5
            ]
            
            if len(project.navigation_pages) < original_length:
                # Update total_pages if it was 5
                if project.total_pages == 5:
                    project.total_pages = 4
                project.save(update_fields=['navigation_pages', 'total_pages'])
                updated_count += 1
    
    print(f"✅ Removed Activity Tracker page from {updated_count} projects")


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_rename_overview_to_project_documents'),
    ]

    operations = [
        migrations.RunPython(add_activity_tracker_page, reverse_add_activity_tracker_page),
    ]


# Generated migration to add System Performance Analysis page to existing projects

from django.db import migrations


def add_system_performance_analysis_page(apps, schema_editor):
    """Add System Performance Analysis as 6th navigation page to existing projects"""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')
    
    system_performance_page = {
        'page_number': 6,
        'name': 'System Performance Analysis',
        'short_name': 'Performance',
        'icon': 'fa-chart-bar',
        'features': ['experiment_metrics', 'performance_analysis', 'system_evaluation']
    }
    
    updated_count = 0
    for project in IntelliDocProject.objects.all():
        if project.navigation_pages:
            # Check if System Performance Analysis page already exists
            has_performance_page = any(
                page.get('name') == 'System Performance Analysis' or page.get('page_number') == 6
                for page in project.navigation_pages
            )
            
            if not has_performance_page:
                # Add System Performance Analysis page
                project.navigation_pages.append(system_performance_page)
                project.total_pages = max(project.total_pages or 5, 6)
                project.save(update_fields=['navigation_pages', 'total_pages'])
                updated_count += 1
    
    print(f"✅ Added System Performance Analysis page to {updated_count} projects")


def reverse_add_system_performance_analysis_page(apps, schema_editor):
    """Reverse migration: remove System Performance Analysis page from projects"""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')
    
    updated_count = 0
    for project in IntelliDocProject.objects.all():
        if project.navigation_pages:
            # Remove System Performance Analysis page
            original_length = len(project.navigation_pages)
            project.navigation_pages = [
                page for page in project.navigation_pages
                if page.get('name') != 'System Performance Analysis' and page.get('page_number') != 6
            ]
            
            if len(project.navigation_pages) < original_length:
                # Update total_pages if it was 6
                if project.total_pages == 6:
                    project.total_pages = 5
                project.save(update_fields=['navigation_pages', 'total_pages'])
                updated_count += 1
    
    print(f"✅ Removed System Performance Analysis page from {updated_count} projects")


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_add_template_version'),
    ]

    operations = [
        migrations.RunPython(
            add_system_performance_analysis_page,
            reverse_add_system_performance_analysis_page
        ),
    ]


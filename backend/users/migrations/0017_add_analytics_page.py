# Migration: insert Analytics page at position 6, shift System Performance → 7, Chatbot → 8

from django.db import migrations


ANALYTICS_PAGE = {
    'page_number': 6,
    'name': 'Analytics',
    'short_name': 'Analytics',
    'icon': 'fa-chart-line',
    'description': 'Agent timing, tool call breakdown, and execution trends',
    'features': ['agent_analytics', 'tool_timing', 'execution_trends'],
}


def add_analytics_page(apps, schema_editor):
    """Insert Analytics as page 6; shift System Performance to 7, Chatbot to 8."""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')

    updated_count = 0
    for project in IntelliDocProject.objects.all():
        if not project.navigation_pages:
            continue

        # Skip if Analytics page already exists
        if any(
            page.get('name') == 'Analytics' or page.get('page_number') == 6
            and page.get('features') and 'agent_analytics' in page.get('features', [])
            for page in project.navigation_pages
        ):
            continue

        changed = False
        for page in project.navigation_pages:
            pn = page.get('page_number')
            if pn == 6:
                # System Performance Analysis → 7
                page['page_number'] = 7
                changed = True
            elif pn == 7:
                # Chatbot → 8
                page['page_number'] = 8
                changed = True

        # Insert Analytics at page 6
        project.navigation_pages.append(ANALYTICS_PAGE)
        project.total_pages = max(project.total_pages or 7, 8)
        project.save(update_fields=['navigation_pages', 'total_pages'])
        updated_count += 1

    print(f"✅ Added Analytics page to {updated_count} projects")


def reverse_add_analytics_page(apps, schema_editor):
    """Reverse: remove Analytics page, shift System Performance back to 6, Chatbot back to 7."""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')

    updated_count = 0
    for project in IntelliDocProject.objects.all():
        if not project.navigation_pages:
            continue

        original_length = len(project.navigation_pages)
        # Remove Analytics page
        project.navigation_pages = [
            page for page in project.navigation_pages
            if page.get('name') != 'Analytics'
            and not (page.get('page_number') == 6 and 'agent_analytics' in page.get('features', []))
        ]

        if len(project.navigation_pages) < original_length:
            for page in project.navigation_pages:
                pn = page.get('page_number')
                if pn == 7 and page.get('name') == 'System Performance Analysis':
                    page['page_number'] = 6
                elif pn == 8:
                    page['page_number'] = 7

            if project.total_pages == 8:
                project.total_pages = 7
            project.save(update_fields=['navigation_pages', 'total_pages'])
            updated_count += 1

    print(f"✅ Removed Analytics page from {updated_count} projects")


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0016_web_search_url_summary'),
    ]

    operations = [
        migrations.RunPython(
            add_analytics_page,
            reverse_add_analytics_page,
        ),
    ]

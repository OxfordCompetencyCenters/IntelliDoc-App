# Generated migration to add Chatbot page to existing projects

from django.db import migrations


def add_chatbot_page(apps, schema_editor):
    """Add Chatbot as 7th navigation page to existing projects"""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')

    chatbot_page = {
        'page_number': 7,
        'name': 'Chatbot',
        'short_name': 'Chatbot',
        'icon': 'fa-comments',
        'features': ['in_app_chatbot']
    }

    updated_count = 0
    for project in IntelliDocProject.objects.all():
        if project.navigation_pages:
            # Check if Chatbot page already exists
            has_chatbot_page = any(
                page.get('name') == 'Chatbot' or page.get('page_number') == 7
                for page in project.navigation_pages
            )

            if not has_chatbot_page:
                # Add Chatbot page
                project.navigation_pages.append(chatbot_page)
                project.total_pages = max(project.total_pages or 6, 7)
                project.save(update_fields=['navigation_pages', 'total_pages'])
                updated_count += 1

    print(f"✅ Added Chatbot page to {updated_count} projects")


def reverse_add_chatbot_page(apps, schema_editor):
    """Reverse migration: remove Chatbot page from projects"""
    IntelliDocProject = apps.get_model('users', 'IntelliDocProject')

    updated_count = 0
    for project in IntelliDocProject.objects.all():
        if project.navigation_pages:
            # Remove Chatbot page
            original_length = len(project.navigation_pages)
            project.navigation_pages = [
                page for page in project.navigation_pages
                if page.get('name') != 'Chatbot' and page.get('page_number') != 7
            ]

            if len(project.navigation_pages) < original_length:
                # Update total_pages if it was 7
                if project.total_pages == 7:
                    project.total_pages = 6
                project.save(update_fields=['navigation_pages', 'total_pages'])
                updated_count += 1

    print(f"✅ Removed Chatbot page from {updated_count} projects")


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_add_llm_file_id_fields'),
    ]

    operations = [
        migrations.RunPython(
            add_chatbot_page,
            reverse_add_chatbot_page
        ),
    ]

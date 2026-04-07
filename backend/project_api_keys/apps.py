# backend/project_api_keys/apps.py

from django.apps import AppConfig

class ProjectApiKeysConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'project_api_keys'
    verbose_name = 'Project API Key Management'

# users/apps.py
from django.apps import AppConfig

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'  # Make sure this matches the name used in INSTALLED_APPS
    
    def ready(self):
        # Import signal handlers
        import users.signals

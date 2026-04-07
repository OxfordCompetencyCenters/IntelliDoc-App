"""
Desktop auto-authentication middleware.
Automatically authenticates all requests as the desktop user.
Used in Electron desktop mode where no login is required.
"""
from django.utils.functional import SimpleLazyObject


def get_desktop_user():
    from users.models import User
    user, created = User.objects.get_or_create(
        email='desktop@localhost',
        defaults={
            'role': 'ADMIN',
            'first_name': 'Desktop',
            'last_name': 'User',
            'is_staff': True,
            'is_superuser': True,
        }
    )
    if created:
        user.set_password('desktop')
        user.save()
    return user


class DesktopAutoAuthMiddleware:
    """Inject the desktop user into every request so IsAuthenticated passes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not hasattr(request, 'user') or request.user.is_anonymous:
            request.user = SimpleLazyObject(get_desktop_user)
            # Also set auth for DRF
            request._force_auth_user = SimpleLazyObject(get_desktop_user)
        return self.get_response(request)

# backend/project_api_keys/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectAPIKeyViewSet

# Create router for ViewSet with @action decorators
router = DefaultRouter()
router.register(r'', ProjectAPIKeyViewSet, basename='project-api-keys')

# Use router URLs only - @action decorators in ViewSet handle the routing
urlpatterns = [
    path('', include(router.urls)),
]

from django.urls import path
from . import ollama_views

urlpatterns = [
    path('status/', ollama_views.ollama_status, name='ollama-status'),
    path('models/', ollama_views.ollama_models, name='ollama-models'),
    path('library/', ollama_views.ollama_library, name='ollama-library'),
    path('pull/', ollama_views.ollama_pull, name='ollama-pull'),
    path('delete/', ollama_views.ollama_delete_model, name='ollama-delete'),
]

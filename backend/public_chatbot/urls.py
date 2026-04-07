"""
URL Configuration for Public Chatbot API
Completely isolated endpoints - no impact on existing AI Catalogue URLs
"""
from django.urls import path
from . import views

app_name = 'public_chatbot'

urlpatterns = [
    # Main public chatbot API endpoint
    path('', views.public_chat_api, name='chat_api'),
    
    # Streaming chatbot API endpoint (Server-Sent Events)
    path('stream/', views.public_chat_stream_api, name='chat_stream_api'),
    
    # Health check endpoint for monitoring
    path('health/', views.health_check, name='health_check'),
]
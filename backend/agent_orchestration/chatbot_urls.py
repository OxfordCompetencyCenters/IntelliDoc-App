from django.urls import path
from . import chatbot_views

urlpatterns = [
    path('<uuid:project_id>/sessions/', chatbot_views.chatbot_sessions, name='chatbot-sessions'),
    path('<uuid:project_id>/sessions/create/', chatbot_views.chatbot_create_session, name='chatbot-create-session'),
    path('<uuid:project_id>/sessions/<uuid:session_id>/', chatbot_views.chatbot_delete_session, name='chatbot-delete-session'),
    path('<uuid:project_id>/sessions/<uuid:session_id>/rename/', chatbot_views.chatbot_rename_session, name='chatbot-rename-session'),
    path('<uuid:project_id>/sessions/<uuid:session_id>/messages/', chatbot_views.chatbot_messages, name='chatbot-messages'),
    path('<uuid:project_id>/sessions/<uuid:session_id>/send/', chatbot_views.chatbot_send_message, name='chatbot-send-message'),
]

"""
URL patterns for Django Milvus Search
"""
from django.urls import path
from . import views

app_name = 'milvus_search'

urlpatterns = [
    # Class-based views
    path('search/', views.MilvusSearchView.as_view(), name='search'),
    path('collections/', views.MilvusCollectionsView.as_view(), name='collections'),
    path('test/', views.MilvusTestView.as_view(), name='test'),
    
    # Function-based views (alternative endpoints)
    path('api/search/', views.search_vectors, name='api_search'),
    path('api/collections/', views.list_collections, name='api_collections'),
    path('api/health/', views.health_check, name='api_health'),
]

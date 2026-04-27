from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('health/', views.health_check, name='health_check'),
    path('api/translate/', views.translate_api, name='translate_api'),
    path('api/process-query/', views.process_query_api, name='process_query'),
    path('api/delete-query/<str:record_id>/', views.delete_query_api, name='delete_query'),
    path('api/retrain/', views.retrain_model_api, name='retrain_model'),
    path('api/model-status/', views.model_status_api, name='model_status'),
]

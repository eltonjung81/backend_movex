from django.urls import path
from . import views

app_name = 'corridas'

urlpatterns = [
    # Using a UUID path converter for corrida_id
    path('corridas/<uuid:corrida_id>/chat/', views.visualizar_mensagens_chat, name='visualizar_mensagens_chat'),
]

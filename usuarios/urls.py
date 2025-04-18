from django.urls import path
from .views import (
    RegistroMotoristaView, 
    LoginView, 
    BuscarDadosMotoristaView, 
    RegistroPassageiroView, 
    LoginPassageiroView, 
    LoginMotoristaView,
    SalvarTokenPushView
)
import logging

logger = logging.getLogger(__name__)
logger.info("Usuarios URLs loaded successfully")

# Remover o namespace que pode estar causando conflitos
# app_name = 'usuarios'

urlpatterns = [
    path('registro/motorista/', RegistroMotoristaView.as_view(), name='registro-motorista'),
    path('registro/passageiro/', RegistroPassageiroView.as_view(), name='registro-passageiro'),
    path('login/', LoginView.as_view(), name='login'),
    path('login/passageiro/', LoginPassageiroView.as_view(), name='login-passageiro'),
    path('salvar-token/', SalvarTokenPushView.as_view(), name='salvar-token-push'),
    # Removendo rotas duplicadas que já estão no arquivo principal
    # path('login/motorista/', LoginMotoristaView.as_view(), name='login-motorista'),
    # path('motorista/buscar_dados/', BuscarDadosMotoristaView.as_view(), name='buscar_dados_motorista'),
]

# Log de URLs registradas para depuração
for url in urlpatterns:
    logger.info(f"URL registrada em usuarios/urls.py: {url.pattern} - nome: {url.name}")
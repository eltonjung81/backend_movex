from django.urls import path
from .views import RegistroMotoristaView, LoginView, BuscarDadosMotoristaView, RegistroPassageiroView, LoginPassageiroView, LoginMotoristaView
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
    # Estas duas rotas abaixo também estão definidas no arquivo principal para garantir o funcionamento
    path('login/motorista/', LoginMotoristaView.as_view(), name='login-motorista'),
    path('motorista/buscar_dados/', BuscarDadosMotoristaView.as_view(), name='buscar_dados_motorista'),
]

# Log de URLs registradas para depuração
for url in urlpatterns:
    logger.info(f"URL registrada em usuarios/urls.py: {url.pattern} - nome: {url.name}")
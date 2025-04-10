import os
import sys
import django
import logging
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from pathlib import Path

logger = logging.getLogger(__name__)
logger.info("Carregando configuração ASGI")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movex.settings')
django.setup()

# Definir BASE_DIR
BASE_DIR = Path(__file__).resolve().parent.parent

# Obter o aplicativo ASGI
django_asgi_app = get_asgi_application()

# Registrar as URLs carregadas no Django
from django.urls import get_resolver
resolver = get_resolver(None)
print("---------- ASGI: URLs carregadas ----------")
for url_pattern in resolver.url_patterns:
    print(f"URL pattern: {url_pattern.pattern}")

# Importar as rotas de websocket após a configuração do Django
from movex.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,  # Apenas o ASGI padrão para HTTP
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})

# Adicionar log para confirmar o carregamento
logger.info("Configuração ASGI carregada com sucesso")
print("---------- ASGI: Configuração Concluída ----------")

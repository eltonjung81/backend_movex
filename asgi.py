import os
import asyncio
import platform
from django.core.asgi import get_asgi_application
from pathlib import Path

# Use a more efficient event loop on Windows
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Set the event loop policy before importing any other modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Import channels modules after setting up the event loop
from channels.routing import ProtocolTypeRouter, URLRouter
import websocket_app.routing

# Agora importamos whitenoise para servir arquivos estáticos
from whitenoise import WhiteNoise

# Define o diretório base do projeto
BASE_DIR = Path(__file__).resolve().parent

# Get ASGI application
django_asgi_app = get_asgi_application()

# Configurar o WhiteNoise para servir arquivos estáticos
staticfiles_path = BASE_DIR / "staticfiles"
if staticfiles_path.exists():
    django_asgi_app = WhiteNoise(django_asgi_app, root=staticfiles_path)
    django_asgi_app.add_files(str(staticfiles_path), prefix="static/")
    print(f"Servindo arquivos estáticos de: {staticfiles_path}")
else:
    print(f"AVISO: Diretório de arquivos estáticos não encontrado em: {staticfiles_path}")

# Configure the ASGI application
application = ProtocolTypeRouter({
    'http': django_asgi_app,  # Agora com suporte para arquivos estáticos via WhiteNoise
    'websocket': URLRouter(
        websocket_app.routing.websocket_urlpatterns
    ),
})

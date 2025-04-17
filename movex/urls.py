from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
import logging
from usuarios.views import LoginMotoristaView, BuscarDadosMotoristaView

logger = logging.getLogger(__name__)
logger.info("Main URLs loaded successfully")

urlpatterns = [
    path('admin/', admin.site.urls),  # Certifique-se de que o painel admin está aqui
    
    # Incluir as URLs explicitamente para evitar problemas de namespace
    path('api/usuarios/', include('usuarios.urls')),
    
    # Adicionar as rotas críticas diretamente no urlpatterns principal
    path('api/usuarios/login/motorista/', LoginMotoristaView.as_view(), name='api_login_motorista'),
    path('api/usuarios/motorista/buscar_dados/', BuscarDadosMotoristaView.as_view(), name='api_buscar_dados_motorista'),
    
    # Tente incluir as URLs de corridas apenas se o módulo existir
    path('api/corridas/', include('corridas.urls', namespace='corridas')),
]

# Adicione depuração de URL
print("---- URLs registradas ----")
for url in urlpatterns:
    print(f"URL pattern: {url.pattern}")

# Add static and media files handling if in debug mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

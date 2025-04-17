import re
from django.conf import settings
import logging
import sys
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class DisableCSRFMiddleware(MiddlewareMixin):
    EXEMPT_URLS = [
        r'^api/usuarios/motorista/buscar_dados/$',
        r'^api/usuarios/motorista/dados/.*$',
        r'^api/usuarios/login/motorista/$',
        r'^api/usuarios/login/passageiro/$',
        r'^api/usuarios/registro/.*$',
        r'^admin/',  # Adicione esta linha para isentar o painel admin
    ]

    def process_request(self, request):
        for exempt_url in self.EXEMPT_URLS:
            if re.match(exempt_url, request.path):
                request.csrf_processing_done = True
                return None
        return None

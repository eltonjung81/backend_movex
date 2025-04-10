import re
from django.conf import settings
import logging
import sys

logger = logging.getLogger(__name__)

class DisableCSRFMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Simplificar a lógica de padrões de URL
        self.csrf_exempt_urls = [
            re.compile(r'^api/usuarios/motorista/buscar_dados/$'),
            re.compile(r'^api/usuarios/motorista/dados/.*$'),
            re.compile(r'^api/usuarios/login/motorista/$'),
            re.compile(r'^api/usuarios/login/passageiro/$'),
            re.compile(r'^api/usuarios/registro/.*$')
        ]
        
        logger.info("DisableCSRFMiddleware inicializado")
        print("DisableCSRFMiddleware inicializado", file=sys.stderr)
        
        # Log dos padrões para depuração
        for pattern in self.csrf_exempt_urls:
            logger.info(f"CSRF exempt URL pattern: {pattern.pattern}")
            print(f"CSRF exempt URL pattern: {pattern.pattern}", file=sys.stderr)

    def __call__(self, request):
        path = request.path_info.lstrip('/')
        print(f"[CSRF] Request path: {path}", file=sys.stderr)
        
        # Verificar se a URL atual corresponde a alguma das URLs isentas
        for pattern in self.csrf_exempt_urls:
            if pattern.match(path):
                print(f"[CSRF] Exemption applied for {path}", file=sys.stderr)
                setattr(request, '_dont_enforce_csrf_checks', True)
                break
        else:
            print(f"[CSRF] No exemption for {path}", file=sys.stderr)  # Log para depuração
        
        response = self.get_response(request)
        return response

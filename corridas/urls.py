from django.urls import path
from django.http import JsonResponse

app_name = 'corridas'

# Rota básica para evitar erros
urlpatterns = [
    path('', lambda request: JsonResponse({'message': 'Corridas API funcionando!'})),
]

# Adicionar log para depuração
import logging
logger = logging.getLogger(__name__)
logger.info("Corridas URLs carregadas com sucesso")

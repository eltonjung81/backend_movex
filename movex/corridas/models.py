from django.db import models
from django.utils import timezone
import uuid
from usuarios.models import Motorista, Passageiro

class Corrida(models.Model):
    # ... campos existentes ...
    
    # Campos para avaliação do motorista (pelo passageiro)
    avaliacao_motorista = models.IntegerField(null=True, blank=True)
    comentario_motorista = models.TextField(null=True, blank=True)
    data_avaliacao_motorista = models.DateTimeField(null=True, blank=True)
    
    # Campos para avaliação do passageiro (pelo motorista)
    avaliacao_passageiro = models.IntegerField(null=True, blank=True)
    comentario_passageiro = models.TextField(null=True, blank=True)
    data_avaliacao_passageiro = models.DateTimeField(null=True, blank=True)
    
    # ... resto do modelo existente ...

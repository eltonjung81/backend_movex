from django.db import models
import uuid
from decimal import Decimal
from django.utils import timezone
from usuarios.models import Passageiro, Motorista







class Corrida(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('ACEITA', 'Aceita'),
        ('MOTORISTA_CHEGOU', 'Motorista Chegou'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('FINALIZADA', 'Finalizada'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    passageiro = models.ForeignKey(Passageiro, on_delete=models.CASCADE, related_name='corridas')
    motorista = models.ForeignKey(Motorista, on_delete=models.SET_NULL, null=True, blank=True, related_name='corridas', to_field='cpf')
    
    # Status e datas
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    data_solicitacao = models.DateTimeField(default=timezone.now)
    data_aceite = models.DateTimeField(null=True, blank=True)
    data_chegada_motorista = models.DateTimeField(null=True, blank=True)
    data_inicio = models.DateTimeField(null=True, blank=True)
    data_fim = models.DateTimeField(null=True, blank=True)


    # Campos para avaliação do motorista (pelo passageiro)
    avaliacao_motorista = models.IntegerField(null=True, blank=True)
    comentario_motorista = models.TextField(null=True, blank=True)
    data_avaliacao_motorista = models.DateTimeField(null=True, blank=True)
    
    # Campos para avaliação do passageiro (pelo motorista)
    avaliacao_passageiro = models.IntegerField(null=True, blank=True)
    comentario_passageiro = models.TextField(null=True, blank=True)
    data_avaliacao_passageiro = models.DateTimeField(null=True, blank=True)
    
    # Origem e destino
    origem_lat = models.DecimalField(max_digits=9, decimal_places=6)
    origem_lng = models.DecimalField(max_digits=9, decimal_places=6)
    origem_descricao = models.CharField(max_length=255, default='Local de origem')
    
    destino_lat = models.DecimalField(max_digits=9, decimal_places=6)
    destino_lng = models.DecimalField(max_digits=9, decimal_places=6)
    destino_descricao = models.CharField(max_length=255, default='Local de destino')
    
    # Informações da corrida
    valor = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    distancia = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))  # em km
    tempo_estimado = models.IntegerField(default=0)  # em minutos
    
    # Informações adicionais do passageiro para esta corrida (opcional)
    info_adicional_passageiro = models.TextField(null=True, blank=True)  # Notas ou informações especiais
    contato_alternativo = models.CharField(max_length=100, null=True, blank=True)  # Contato alternativo se necessário
    
    # Gerenciamento de cancelamentos
    motivo_cancelamento = models.TextField(null=True, blank=True)
    cancelada_por_tipo = models.CharField(max_length=20, null=True, blank=True)  # PASSAGEIRO ou MOTORISTA
    cancelada_por_cpf = models.CharField(max_length=14, null=True, blank=True)
    data_cancelamento = models.DateTimeField(null=True, blank=True)
    
    # Campos para gerenciar desconexões do motorista
    motorista_temporariamente_desconectado = models.BooleanField(default=False)
    
    # Avaliações
    avaliacao_motorista = models.IntegerField(null=True, blank=True)  # 1 a 5 estrelas
    avaliacao_passageiro = models.IntegerField(null=True, blank=True)  # 1 a 5 estrelas
    comentario_motorista = models.TextField(null=True, blank=True)
    comentario_passageiro = models.TextField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Corrida'
        verbose_name_plural = 'Corridas'
        ordering = ['-data_solicitacao']
    
    def __str__(self):
        motorista_nome = self.motorista.usuario.get_full_name() if self.motorista else "Não atribuído"
        return f'Corrida {self.id} - {self.passageiro.usuario.get_full_name()} com {motorista_nome} - {self.status}'

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
    
    def obter_mensagens_chat(self):
        """
        Retorna todas as mensagens de chat desta corrida, ordenadas por data de envio
        """
        return self.mensagens.all().order_by('data_envio')
    
    def contar_mensagens_nao_lidas(self, tipo_destinatario):
        """
        Conta quantas mensagens não lidas existem para um tipo de destinatário
        
        Args:
            tipo_destinatario: 'PASSAGEIRO' ou 'MOTORISTA'
        
        Returns:
            int: Número de mensagens não lidas
        """
        # Se o destinatário é PASSAGEIRO, o remetente é MOTORISTA e vice-versa
        tipo_remetente = 'MOTORISTA' if tipo_destinatario == 'PASSAGEIRO' else 'PASSAGEIRO'
        return self.mensagens.filter(tipo_remetente=tipo_remetente, lida=False).count()


class MensagemChat(models.Model):
    TIPO_REMETENTE_CHOICES = [
        ('PASSAGEIRO', 'Passageiro'),
        ('MOTORISTA', 'Motorista'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    corrida = models.ForeignKey('Corrida', on_delete=models.CASCADE, related_name='mensagens')
    tipo_remetente = models.CharField(max_length=20, choices=TIPO_REMETENTE_CHOICES, db_index=True)
    conteudo = models.TextField()
    data_envio = models.DateTimeField(auto_now_add=True, db_index=True)
    lida = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        ordering = ['data_envio']
        indexes = [
            models.Index(fields=['corrida', 'tipo_remetente']),
            models.Index(fields=['corrida', 'lida']),
            models.Index(fields=['corrida', 'data_envio'])
        ]
    
    def __str__(self):
        return f"Mensagem de {self.tipo_remetente} em {self.data_envio}"

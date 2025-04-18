from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from decimal import Decimal

class UsuarioManager(BaseUserManager):
    def create_user(self, cpf, password=None, **extra_fields):
        if not cpf:
            raise ValueError('CPF é obrigatório')
        user = self.model(cpf=cpf, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, cpf, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('tipo_usuario', 'ADMINISTRADOR')  # Define o tipo como ADMINISTRADOR

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser deve ter is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser deve ter is_superuser=True')
        if extra_fields.get('tipo_usuario') != 'ADMINISTRADOR':
            raise ValueError('Superuser deve ter tipo_usuario=ADMINISTRADOR')

        return self.create_user(cpf, password, **extra_fields)

class Usuario(AbstractBaseUser, PermissionsMixin):
    CPF_MAX_LENGTH = 14
    
    TIPO_CHOICES = [
        ('PASSAGEIRO', 'Passageiro'),
        ('MOTORISTA', 'Motorista'),
        ('ADMINISTRADOR', 'Administrador'),
        ('DIRETOR', 'Diretor'),  # Novo tipo de usuário
    ]
    
    cpf = models.CharField(max_length=CPF_MAX_LENGTH, unique=True)
    nome = models.CharField(max_length=100)
    sobrenome = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=20)
    data_nascimento = models.DateField(null=True, blank=True)
    
    tipo_usuario = models.CharField(max_length=20, choices=TIPO_CHOICES, default='PASSAGEIRO')
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    data_cadastro = models.DateTimeField(default=timezone.now)
    
    objects = UsuarioManager()
    
    USERNAME_FIELD = 'cpf'
    REQUIRED_FIELDS = ['nome', 'sobrenome', 'email', 'telefone']
    
    def get_full_name(self):
        return f'{self.nome} {self.sobrenome}'
    
    def get_short_name(self):
        return self.nome
    
    def __str__(self):
        return f'{self.get_full_name()} ({self.cpf})'
    
    def save(self, *args, **kwargs):
        # Garantir que o usuário "Diretor" tenha todas as permissões
        if self.tipo_usuario == 'DIRETOR':
            self.is_staff = True
            self.is_superuser = True
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'

class Passageiro(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, primary_key=True)
    foto_perfil = models.ImageField(upload_to='passageiros/', null=True, blank=True)
    avaliacao_media = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('0.0'))
    endereco = models.CharField(max_length=255, blank=True, null=True)  # Adicionando o campo endereco
    
    def __str__(self):
        return f'Passageiro: {self.usuario.get_full_name()}'
    
    class Meta:
        verbose_name = 'Passageiro'
        verbose_name_plural = 'Passageiros'

class Motorista(models.Model):
    STATUS_CHOICES = [
        ('DISPONIVEL', 'Disponível'),
        ('OCUPADO', 'Ocupado'),
        ('OFFLINE', 'Offline'),
        ('INATIVO', 'Inativo'),
    ]
    
    # Agora o CPF é a chave primária
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='motorista')
    cpf = models.CharField(max_length=14, primary_key=True)
    cnh = models.CharField(max_length=20, unique=True)
    categoria_cnh = models.CharField(max_length=5)
    foto_perfil = models.ImageField(upload_to='motoristas/', null=True, blank=True)
    avaliacao_media = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('0.0'))
    
    # Dados do veículo
    modelo_veiculo = models.CharField(max_length=100)
    ano_veiculo = models.IntegerField()
    placa_veiculo = models.CharField(max_length=10)
    cor_veiculo = models.CharField(max_length=50)
    
    # Status e localização
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OFFLINE')
    esta_disponivel = models.BooleanField(default=False)
    ultima_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    ultima_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    ultima_atualizacao_localizacao = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f'Motorista: {self.usuario.get_full_name()} ({self.placa_veiculo})'
    
    def save(self, *args, **kwargs):
        # Garantir que o CPF seja o mesmo do usuário associado
        if not self.cpf and self.usuario:
            self.cpf = self.usuario.cpf
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = 'Motorista'
        verbose_name_plural = 'Motoristas'

class PushToken(models.Model):
    """Modelo para armazenar tokens de notificação push dos usuários"""
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='push_token')
    token = models.CharField(max_length=255)
    plataforma = models.CharField(max_length=50, default='expo') # 'expo', 'fcm', etc.
    ativo = models.BooleanField(default=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Token de {self.usuario.get_full_name()} - {'Ativo' if self.ativo else 'Inativo'}"
    
    class Meta:
        verbose_name = 'Token Push'
        verbose_name_plural = 'Tokens Push'
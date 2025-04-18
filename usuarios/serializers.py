from rest_framework import serializers
from .models import Usuario, Motorista, Passageiro, PushToken
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

class UsuarioSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = Usuario
        fields = ['cpf', 'nome', 'sobrenome', 'telefone', 'email', 'data_nascimento', 'password', 'password2']
        extra_kwargs = {
            'password': {'write_only': True},
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password2'):
            raise serializers.ValidationError({"password": "As senhas não conferem"})
        return attrs

class LoginSerializer(serializers.Serializer):
    cpf = serializers.CharField(max_length=14, required=True)
    password = serializers.CharField(required=True, write_only=True)

class MotoristaSerializer(serializers.ModelSerializer):
    usuario = UsuarioSerializer(required=True)
    
    class Meta:
        model = Motorista
        fields = ['usuario', 'cnh', 'categoria_cnh', 'placa_veiculo', 'modelo_veiculo', 'cor_veiculo', 'ano_veiculo']
        # Removido 'cpf' dos campos, já que será preenchido automaticamente com o CPF do usuário
        extra_kwargs = {
            'ano_veiculo': {'required': False, 'default': 2023},
            'cor_veiculo': {'required': False, 'default': 'Não informado'},
        }
    
    @transaction.atomic
    def create(self, validated_data):
        usuario_data = validated_data.pop('usuario')
        password = usuario_data.pop('password')
        
        # Verificar se email foi fornecido e definir um valor padrão se necessário
        if 'email' not in usuario_data or not usuario_data['email']:
            # Usar CPF como parte do email padrão para garantir unicidade
            cpf = usuario_data.get('cpf', '').replace('.', '').replace('-', '')
            usuario_data['email'] = f"motorista_{cpf}@movex.com"
        
        # Cria o usuário com tipo MOTORISTA
        usuario = Usuario.objects.create(
            **usuario_data,
            tipo_usuario='MOTORISTA'
        )
        usuario.set_password(password)
        usuario.save()
        
        # Adiciona um valor padrão para campos se não estiverem presentes
        if 'ano_veiculo' not in validated_data:
            validated_data['ano_veiculo'] = 2023
        
        if 'cor_veiculo' not in validated_data:
            validated_data['cor_veiculo'] = 'Não informado'
        
        # Cria o motorista associado ao usuário, usando o CPF do usuário
        motorista = Motorista.objects.create(
            usuario=usuario,
            cpf=usuario.cpf,  # Define explicitamente o CPF do motorista como o do usuário
            **validated_data
        )
        
        return motorista

class PassageiroSerializer(serializers.ModelSerializer):
    class Meta:
        model = Passageiro
        fields = []  # Removendo o campo 'endereco' que não existe no modelo

class RegistroPassageiroSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(write_only=True, required=True)
    passageiro = PassageiroSerializer(required=False)

    class Meta:
        model = Usuario
        fields = ['cpf', 'nome', 'sobrenome', 'password', 'password2', 'telefone', 'email', 'data_nascimento', 'passageiro']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}  # Tornando email obrigatório
        }

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password2'):
            raise serializers.ValidationError({"password": "As senhas não conferem"})
        return attrs

    def create(self, validated_data):
        print(f"[DEBUG] Dados validados: {validated_data}")  # Log para debug
        passageiro_data = validated_data.pop('passageiro', {})
        password = validated_data.pop('password')  # Remove a senha para criar_usuario separadamente
        
        try:
            # Criar o usuário com o tipo correto
            usuario = Usuario.objects.create(
                **validated_data,
                tipo_usuario='PASSAGEIRO'
            )
            usuario.set_password(password)  # Define a senha corretamente
            usuario.save()
            
            # Criar o registro de passageiro
            Passageiro.objects.create(usuario=usuario, **passageiro_data)
            
            return usuario
        except Exception as e:
            print(f"[DEBUG] Erro na criação: {str(e)}")  # Log para debug
            raise

class LoginPassageiroSerializer(serializers.Serializer):
    cpf = serializers.CharField()
    password = serializers.CharField()

class PushTokenSerializer(serializers.ModelSerializer):
    cpf = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = PushToken
        fields = ['token', 'cpf', 'plataforma']
        extra_kwargs = {'plataforma': {'required': False, 'default': 'expo'}}
        
    def create(self, validated_data):
        cpf = validated_data.pop('cpf')
        try:
            usuario = Usuario.objects.get(cpf=cpf)
            # Verificar se já existe um token para este usuário
            token_existente = PushToken.objects.filter(usuario=usuario).first()
            
            if token_existente:
                # Atualizar token existente
                token_existente.token = validated_data.get('token')
                token_existente.plataforma = validated_data.get('plataforma', token_existente.plataforma)
                token_existente.ativo = True
                token_existente.save()
                return token_existente
            else:
                # Criar novo token
                return PushToken.objects.create(
                    usuario=usuario,
                    **validated_data
                )
        except Usuario.DoesNotExist:
            raise serializers.ValidationError({"cpf": "Usuário não encontrado com este CPF"})
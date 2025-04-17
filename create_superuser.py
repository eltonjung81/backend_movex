import os
import django
import sys

# Configurar as configurações do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movex.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError

Usuario = get_user_model()

def create_superuser():
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@movex.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
    
    # Valores para os campos adicionais do modelo personalizado Usuario
    nome = 'Admin'
    sobrenome = 'MoveX'
    cpf = '00000000000'  # CPF fictício para o admin
    telefone = '0000000000'
    tipo_usuario = 'ADMIN'
    
    try:
        # Verificar se o superusuário já existe
        if Usuario.objects.filter(username=username).exists():
            print(f"Superusuário '{username}' já existe. Pulando criação.")
            return
        
        # Criar o superusuário com os campos personalizados
        superuser = Usuario.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            nome=nome,
            sobrenome=sobrenome,
            cpf=cpf,
            telefone=telefone,
            tipo_usuario=tipo_usuario
        )
        
        print(f"Superusuário '{username}' criado com sucesso!")
    except IntegrityError as e:
        print(f"Erro ao criar superusuário: {e}")
    except Exception as e:
        print(f"Erro inesperado: {e}")

if __name__ == "__main__":
    print("Iniciando criação do superusuário...")
    create_superuser()
    print("Processo concluído!")

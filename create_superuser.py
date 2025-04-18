import os
import django
import sys

# Configurar o ambiente Django
sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "movex.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError

Usuario = get_user_model()

def create_superuser():
    # Dados do superuser
    cpf = "00000000000"  # CPF do administrador
    nome = "Admin"
    sobrenome = "MoveX"
    email = "admin@movex.com"
    telefone = "0000000000"
    password = "admin123"  # Defina uma senha forte em ambiente de produção!
    
    try:
        # Verificar se já existe um usuário com este CPF
        if Usuario.objects.filter(cpf=cpf).exists():
            print(f"Usuário com CPF {cpf} já existe. Atualizando para superuser...")
            user = Usuario.objects.get(cpf=cpf)
        else:
            # Criar um novo usuário
            user = Usuario(
                cpf=cpf,
                nome=nome,
                sobrenome=sobrenome,
                email=email,
                telefone=telefone,
                tipo_usuario="ADMINISTRADOR"  # Define o tipo como ADMINISTRADOR
            )
        
        # Definir permissões de superuser
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        
        print(f"Superuser criado/atualizado com sucesso!")
        print(f"CPF: {cpf}")
        print(f"Nome: {nome} {sobrenome}")
        print(f"Email: {email}")
        print(f"Senha: {password}")
        print(f"Acesse o admin em: http://127.0.0.1:8000/admin/")
        
    except IntegrityError as e:
        print(f"Erro ao criar superuser: {e}")
    except Exception as e:
        print(f"Erro inesperado: {e}")

def create_diretor():
    # Dados do diretor
    cpf = "11111111111"  # CPF do diretor
    nome = "Diretor"
    sobrenome = "MoveX"
    email = "diretor@movex.com"
    telefone = "51999999999"
    password = "diretor123"  # Defina uma senha forte em produção!
    
    # Criar ou atualizar o usuário "Diretor"
    diretor, created = Usuario.objects.update_or_create(
        cpf=cpf,
        defaults={
            "nome": nome,
            "sobrenome": sobrenome,
            "email": email,
            "telefone": telefone,
            "tipo_usuario": "DIRETOR",
            "is_staff": True,
            "is_superuser": True,
        }
    )
    diretor.set_password(password)
    diretor.save()

    print(f"Usuário Diretor {'criado' if created else 'atualizado'} com sucesso!")
    print(f"CPF: {cpf}")
    print(f"Nome: {nome} {sobrenome}")
    print(f"Email: {email}")
    print(f"Senha: {password}")

if __name__ == "__main__":
    create_superuser()
    create_diretor()

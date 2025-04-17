import os
import sys
import django
from django.core.management import call_command

# Configurar as configurações do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movex.settings')
django.setup()

if __name__ == "__main__":
    print("Iniciando migrações do banco de dados...")
    try:
        call_command('migrate')
        print("Migrações concluídas com sucesso!")
    except Exception as e:
        print(f"Erro ao executar migrações: {e}")
        sys.exit(1)
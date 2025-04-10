import os
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise
import django
from django.core.management import call_command
import subprocess

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movex.settings')

# Rodar migrações automaticamente ao iniciar o servidor
try:
    django.setup()
    call_command('migrate')
except Exception as e:
    print(f"Erro ao aplicar migrações: {e}")

# Executar o script para criar superusuário e diretor automaticamente
try:
    subprocess.run(['python', 'create_superuser.py'], check=True)
except Exception as e:
    print(f"Erro ao executar o script create_superuser.py: {e}")

# Configuração do WSGI com WhiteNoise
application = get_wsgi_application()
application = WhiteNoise(application, root=os.path.join(os.path.dirname(__file__), 'staticfiles'))

import os
import zipfile
import shutil

# Arquivos e diretórios a incluir
INCLUDE_DIRS = [
    'movex',
    'corridas',
    'usuarios',
    'templates',
    'static',
]

# Arquivos na raiz a incluir
ROOT_FILES = [
    'manage.py',
    'requirements.txt',
    'gunicorn.conf.py',
    'Procfile',
]

# Arquivos e diretórios a excluir
EXCLUDE_PATTERNS = [
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '.git',
    '.env',
    'venv',
    'db.sqlite3',
]

# Criar diretório temporário para organizar os arquivos
if os.path.exists('glitch_upload'):
    shutil.rmtree('glitch_upload')
os.makedirs('glitch_upload')

def should_exclude(path):
    for pattern in EXCLUDE_PATTERNS:
        if pattern in path:
            return True
        if pattern.endswith('*') and path.startswith(pattern[:-1]):
            return True
    return False

def copy_to_temp(src, dest):
    if os.path.isdir(src):
        if should_exclude(src):
            return
        
        if not os.path.exists(dest):
            os.makedirs(dest)
        
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dest, item)
            copy_to_temp(s, d)
    else:
        if not should_exclude(src):
            shutil.copy2(src, dest)

# Copiar diretórios principais
for dir_name in INCLUDE_DIRS:
    if os.path.exists(dir_name):
        copy_to_temp(dir_name, os.path.join('glitch_upload', dir_name))

# Copiar arquivos da raiz
for file_name in ROOT_FILES:
    if os.path.exists(file_name):
        shutil.copy2(file_name, os.path.join('glitch_upload', file_name))

# Criar arquivo glitch.json para configurar o projeto
with open(os.path.join('glitch_upload', 'glitch.json'), 'w') as f:
    f.write('''{
  "install": "pip install -r requirements.txt",
  "start": "gunicorn movex.asgi:application -k uvicorn.workers.UvicornWorker",
  "watch": {
    "ignore": [
      "\\\\.pyc$"
    ],
    "install": {
      "include": [
        "^requirements\\\\.txt$"
      ]
    },
    "restart": {
      "include": [
        "\\\\.py$",
        "^manage\\\\.py$"
      ]
    }
  }
}''')

# Criar um arquivo start.sh para facilitar o início do servidor
with open(os.path.join('glitch_upload', 'start.sh'), 'w') as f:
    f.write('''#!/bin/bash
# Executar migrações do Django
python manage.py migrate

# Iniciar o servidor usando Gunicorn com workers Uvicorn para suporte ASGI
gunicorn movex.asgi:application -k uvicorn.workers.UvicornWorker -b 0.0.0.0:3000
''')

# Criar arquivo .env para variáveis de ambiente
with open(os.path.join('glitch_upload', '.env'), 'w') as f:
    f.write('''DEBUG=True
SECRET_KEY=glitch-development-key-change-this-in-production
ALLOWED_HOSTS=.glitch.me,localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
''')

# Criar o arquivo ZIP para upload
with zipfile.ZipFile('movex_for_glitch.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk('glitch_upload'):
        for file in files:
            file_path = os.path.join(root, file)
            zipf.write(file_path, arcname=file_path.replace('glitch_upload/', ''))

print(f"Arquivo ZIP criado: movex_for_glitch.zip")
print("Faça upload deste arquivo para o Glitch descompactando-o no terminal com:")
print("unzip /tmp/movex_for_glitch.zip -d .")
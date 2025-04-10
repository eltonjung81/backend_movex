from pathlib import Path
import os

# Define BASE_DIR como o diretório base do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

# Diretório onde os arquivos estáticos coletados serão armazenados
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Diretórios onde Django procura arquivos estáticos durante o desenvolvimento
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, '..', 'static'),  # Acessa a pasta static na raiz do projeto, se necessário
]

# Configure WhiteNoise no middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # ...other middleware...
]

# Ativa o armazenamento otimizado de arquivos estáticos do WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
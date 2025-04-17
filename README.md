# MoveX Backend

Backend da aplicação MoveX para serviços de transporte, implementado usando Django e Django Channels para comunicação em tempo real.

## Tecnologias

- Python 3.11+
- Django 5.0+
- Django Channels para WebSockets
- Django REST Framework para APIs
- Gunicorn + Uvicorn para servidor ASGI

## Configuração de Desenvolvimento

### Pré-requisitos

- Python 3.11 ou superior
- pip (gerenciador de pacotes Python)
- Ambiente virtual (recomendado)

### Instalação

1. Clone o repositório
```
git clone https://github.com/seu-usuario/movex-backend.git
cd movex-backend
```

2. Crie e ative um ambiente virtual
```
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows
```

3. Instale as dependências
```
pip install -r requirements.txt
```

4. Execute as migrações
```
python manage.py migrate
```

5. Inicie o servidor de desenvolvimento
```
python manage.py runserver
```

Para WebSockets (desenvolvimento):
```
python manage.py runserver
```

Para WebSockets (produção):
```
gunicorn movex.asgi:application -k uvicorn.workers.UvicornWorker
```

## API Endpoints

- `/api/usuarios/` - Gerenciamento de usuários
- `/api/corridas/` - Gerenciamento de corridas

## WebSocket Endpoints

- `/ws/corridas/` - Comunicação em tempo real para corridas

## Deployment

O projeto está configurado para deploy em várias plataformas:

- Render: usando `render.yaml`
- Fly.io: usando `fly.toml`
- Heroku: usando `Procfile`
- Railway: usando `railway.json`
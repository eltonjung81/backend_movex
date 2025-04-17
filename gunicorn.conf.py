import multiprocessing

# Configurações do Gunicorn
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"  # Usar worker ASGI do Uvicorn
timeout = 120
keepalive = 5
errorlog = "-"
accesslog = "-"
loglevel = "info"
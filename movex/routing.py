from django.urls import path, re_path
from movex.consumers import MoveXConsumer, ChatConsumer

websocket_urlpatterns = [
    path('ws/movex/', MoveXConsumer.as_asgi()),
    path('ws/chat/<str:room_name>/', ChatConsumer.as_asgi()),
    # Rotas para conexão do motorista (com e sem barra final)
    re_path(r'motorista/$', MoveXConsumer.as_asgi()),
    re_path(r'motorista/?$', MoveXConsumer.as_asgi()),  # Aceita com ou sem barra no final
    # Rotas alternativas com prefixo ws para compatibilidade
    re_path(r'ws/motorista/$', MoveXConsumer.as_asgi()),
    re_path(r'ws/motorista/?$', MoveXConsumer.as_asgi()),
]

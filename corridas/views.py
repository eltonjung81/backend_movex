from django.shortcuts import render, get_object_or_404
from .models import Corrida, MensagemChat
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from movex.database_services import limpar_corrida_da_memoria  # Importar a função

@staff_member_required  # Restringe acesso apenas para staff
def visualizar_mensagens_chat(request, corrida_id):
    """View para visualizar mensagens de chat de uma corrida específica"""
    corrida = get_object_or_404(Corrida, id=corrida_id)
    mensagens = corrida.mensagens.all().order_by('data_envio')
    
    # Se a corrida foi removida ou cancelada, limpar das variáveis em memória
    if request.method == 'POST' and 'remover_corrida' in request.POST:
        limpar_corrida_da_memoria(corrida_id)
    
    return render(request, 'corridas/chat_mensagens.html', {
        'corrida': corrida,
        'mensagens': mensagens,
        'title': f'Chat da Corrida {corrida_id}'
    })

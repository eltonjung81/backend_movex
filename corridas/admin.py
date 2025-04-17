from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Corrida, MensagemChat
from movex.database_services import limpar_corrida_da_memoria

class MensagemInline(admin.TabularInline):
    model = MensagemChat
    extra = 0
    readonly_fields = ('data_envio',)

@admin.register(Corrida)
class CorridaAdmin(admin.ModelAdmin):
    list_display = ('id', 'passageiro', 'motorista', 'status', 'data_solicitacao', 'data_aceite', 'valor')
    list_filter = ('status', 'data_solicitacao')
    search_fields = ('id', 'passageiro__usuario__nome', 'motorista__usuario__nome')
    readonly_fields = ('data_solicitacao', 'data_aceite', 'data_fim')
    inlines = [MensagemInline]

    def delete_model(self, request, obj):
        """Sobrescreve o método delete_model para limpar a corrida da memória antes de excluí-la"""
        corrida_id = obj.id
        super().delete_model(request, obj)
        limpar_corrida_da_memoria(corrida_id)
    
    def delete_queryset(self, request, queryset):
        """Sobrescreve o método delete_queryset para limpar as corridas da memória antes de excluí-las"""
        corrida_ids = list(queryset.values_list('id', flat=True))
        super().delete_queryset(request, queryset)
        for corrida_id in corrida_ids:
            limpar_corrida_da_memoria(corrida_id)

@admin.register(MensagemChat)
class MensagemChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'corrida', 'tipo_remetente', 'conteudo_truncado', 'data_envio', 'lida')
    list_filter = ('tipo_remetente', 'data_envio', 'lida')
    search_fields = ('corrida__id', 'conteudo')
    readonly_fields = ('data_envio',)
    
    def conteudo_truncado(self, obj):
        """Exibe uma versão truncada do conteúdo"""
        if len(obj.conteudo) > 50:
            return f"{obj.conteudo[:50]}..."
        return obj.conteudo
    conteudo_truncado.short_description = 'Conteúdo'

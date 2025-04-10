from django.contrib import admin
from .models import Corrida

class CorridaAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_passageiro', 'get_motorista', 'status', 'valor', 'data_solicitacao', 'data_fim')
    search_fields = ('id', 'passageiro__usuario__nome', 'motorista__usuario__nome', 'origem_descricao', 'destino_descricao')
    list_filter = ('status',)
    date_hierarchy = 'data_solicitacao'
    
    def get_passageiro(self, obj):
        if obj.passageiro:
            return obj.passageiro.usuario.get_full_name()
        return "N/A"
    get_passageiro.short_description = 'Passageiro'
    
    def get_motorista(self, obj):
        if obj.motorista:
            return obj.motorista.usuario.get_full_name()
        return "Não atribuído"
    get_motorista.short_description = 'Motorista'

admin.site.register(Corrida, CorridaAdmin)

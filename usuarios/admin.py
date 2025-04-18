from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import Usuario, Passageiro, Motorista, PushToken
from corridas.models import Corrida

class CustomAdminSite(admin.AdminSite):
    site_header = "Painel de Administração MoveX"
    site_title = "Administração MoveX"
    index_title = "Bem-vindo ao Painel de Administração MoveX"

    def each_context(self, request):
        context = super().each_context(request)
        context['custom_css'] = 'admin/custom_admin.css'
        return context

admin_site = CustomAdminSite(name='custom_admin')

class UsuarioAdmin(UserAdmin):
    list_display = ('cpf', 'nome', 'sobrenome', 'email', 'telefone', 'tipo_usuario', 'is_active', 'is_staff')
    search_fields = ('cpf', 'nome', 'sobrenome', 'email')
    list_filter = ('tipo_usuario', 'is_active', 'is_staff', 'is_superuser')

    fieldsets = (
        (None, {'fields': ('cpf', 'password')}),
        ('Informações Pessoais', {'fields': ('nome', 'sobrenome', 'email', 'telefone', 'data_nascimento')}),
        ('Permissões', {'fields': ('tipo_usuario', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('cpf', 'nome', 'sobrenome', 'email', 'telefone', 'password1', 'password2'),
        }),
    )

    ordering = ('cpf',)

class PassageiroAdmin(admin.ModelAdmin):
    list_display = ('get_cpf', 'get_nome', 'get_email', 'avaliacao_media')
    search_fields = ('usuario__cpf', 'usuario__nome', 'usuario__email')

    def get_cpf(self, obj):
        return obj.usuario.cpf
    get_cpf.short_description = 'CPF'

    def get_nome(self, obj):
        return obj.usuario.get_full_name()
    get_nome.short_description = 'Nome Completo'

    def get_email(self, obj):
        return obj.usuario.email
    get_email.short_description = 'Email'

class MotoristaAdmin(admin.ModelAdmin):
    list_display = ('get_cpf', 'get_nome', 'cnh', 'modelo_veiculo', 'placa_veiculo', 'status', 'esta_disponivel')
    search_fields = ('usuario__cpf', 'usuario__nome', 'cnh', 'placa_veiculo')
    list_filter = ('status', 'esta_disponivel')

    def get_cpf(self, obj):
        return obj.usuario.cpf
    get_cpf.short_description = 'CPF'

    def get_nome(self, obj):
        return obj.usuario.get_full_name()
    get_nome.short_description = 'Nome Completo'

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

# Registrar os modelos no admin personalizado
admin_site.register(Usuario, UsuarioAdmin)
admin_site.register(Passageiro, PassageiroAdmin)
admin_site.register(Motorista, MotoristaAdmin)
admin_site.register(Corrida, CorridaAdmin)

# Registrar os modelos no painel de administração
admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Motorista, MotoristaAdmin)
admin.site.register(Passageiro, PassageiroAdmin)
admin.site.register(PushToken)  # Registrando o novo modelo PushToken

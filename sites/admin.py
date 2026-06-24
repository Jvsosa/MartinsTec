from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Site, SiteFile, SiteRescheduleHistory

# Configuração do painel de administração do Usuário Customizado
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Informações de Cargo', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informações de Cargo', {'fields': ('role',)}),
    )

class SiteRescheduleHistoryInline(admin.TabularInline):
    model = SiteRescheduleHistory
    extra = 0
    readonly_fields = ['previous_planned_survey_date', 'new_planned_survey_date', 'previous_planned_report_date', 'new_planned_report_date', 'reason', 'created_at', 'created_by']
    can_delete = False

# Configuração do painel de administração do Site
class SiteAdmin(admin.ModelAdmin):
    list_display = ['site_id', 'name', 'latitude', 'longitude', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['site_id', 'name']
    inlines = [SiteRescheduleHistoryInline]

# Configuração do painel de administração de Arquivos
class SiteFileAdmin(admin.ModelAdmin):
    list_display = ['site', 'category', 'uploaded_by', 'uploaded_at']
    list_filter = ['category', 'uploaded_at']
    search_fields = ['site__site_id', 'file']

# Registra os modelos no Admin do Django
admin.site.register(User, CustomUserAdmin)
admin.site.register(Site, SiteAdmin)
admin.site.register(SiteFile, SiteFileAdmin)

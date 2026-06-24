import os
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

# --- 1. MODELO DE USUÁRIO COM CONTROLE DE ACESSO POR CARGO (RBAC) ---
class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador'
        ENGINEER = 'ENGINEER', 'Engenheiro'
        TECHNICIAN = 'TECHNICIAN', 'Técnico de Campo'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.TECHNICIAN,
        verbose_name="Cargo / Nível de Acesso"
    )

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


# --- 2. CADASTRO DE SITES DE TELECOM ---
class Site(models.Model):
    class SiteStatus(models.TextChoices):
        PLANNED = 'PLANNED', 'Cadastrado'
        ACTIVE = 'ACTIVE', 'Finalizado'
        MAINTENANCE = 'MAINTENANCE', 'Em Alerta'
        INACTIVE = 'INACTIVE', 'Prazo Vencido'

    class ScopeType(models.TextChoices):
        LAUDOS = 'LAUDOS', 'Laudos'
        INSTALACAO = 'INSTALACAO', 'Instalação'
        INFRA = 'INFRA', 'Infra'
        FABRICA = 'FABRICA', 'Fabrica'

    class SiteType(models.TextChoices):
        ROOFTOP = 'ROOFTOP', 'Rooftop'
        GREENFIELD = 'GREENFIELD', 'Greenfield'
        INDOOR = 'INDOOR', 'Indoor'
        STREET = 'STREET', 'Street'

    class AccessStatus(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', 'Não Iniciado'
        REQUESTED = 'REQUESTED', 'Acesso Solicitado'
        RELEASED = 'RELEASED', 'Acesso Liberado'
        NOT_REQUIRED = 'NOT_REQUIRED', 'Acesso Não Necessário'

    class Operator(models.TextChoices):
        VIVO = 'VIVO', 'Vivo'
        TIM = 'TIM', 'Tim'
        CLARO = 'CLARO', 'Claro'
        OI = 'OI', 'Oi'
        OUTRO = 'OUTRO', 'Outro'

    site_id = models.CharField(
        max_length=50, 
        unique=True, 
        blank=True,
        null=True,
        verbose_name="ID do Site (Código)"
    )
    name = models.CharField(max_length=100, verbose_name="Nome do Site")
    operator = models.CharField(
        max_length=20,
        choices=Operator.choices,
        blank=True,
        null=True,
        verbose_name="Operadora"
    )
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Endereço")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, verbose_name="Latitude")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, verbose_name="Longitude")
    
    # Campo de escopo e parceiro
    scope_type = models.CharField(
        max_length=20,
        choices=ScopeType.choices,
        default=ScopeType.LAUDOS,
        verbose_name="Escopo do Acionamento"
    )
    partner_company = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Fornecedora de Laudo/Projeto"
    )

    # Campos de Fluxo de Acesso do Rollout
    site_type = models.CharField(
        max_length=20,
        choices=SiteType.choices,
        default=SiteType.ROOFTOP,
        verbose_name="Tipo de Estrutura"
    )
    access_status = models.CharField(
        max_length=20,
        choices=AccessStatus.choices,
        default=AccessStatus.NOT_STARTED,
        verbose_name="Situação do Acesso"
    )
    access_requested_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="Acesso Solicitado em"
    )
    access_released_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="Acesso Liberado em"
    )
    reschedule_count = models.IntegerField(
        default=0,
        verbose_name="Quantidade de Replanejamentos"
    )
    stages_status = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Status das Etapas"
    )

    # Datas de Planejamento e Realização do Fluxo
    planned_survey_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="Vistoria Planejada"
    )
    actual_survey_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="Vistoria Realizada"
    )
    planned_report_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="Laudo Planejado"
    )
    actual_report_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="Laudo Realizado"
    )

    status = models.CharField(
        max_length=20,
        choices=SiteStatus.choices,
        default=SiteStatus.PLANNED,
        verbose_name="Status Operacional"
    )
    description = models.TextField(blank=True, null=True, verbose_name="Descrição / Observações")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Cadastrado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Site de Telecom"
        verbose_name_plural = "Sites de Telecom"
        ordering = ['site_id']

    def __str__(self):
        return f"{self.site_id} - {self.name}"

    @property
    def days_overdue(self):
        from django.utils import timezone
        today = timezone.localdate()
        max_delay = 0
        if self.planned_survey_date and not self.actual_survey_date and self.planned_survey_date < today:
            delay = (today - self.planned_survey_date).days
            if delay > max_delay:
                max_delay = delay
        if self.planned_report_date and not self.actual_report_date and self.planned_report_date < today:
            delay = (today - self.planned_report_date).days
            if delay > max_delay:
                max_delay = delay
        return max_delay

    @property
    def overdue_stage(self):
        from django.utils import timezone
        today = timezone.localdate()
        stages = []
        if self.planned_survey_date and not self.actual_survey_date and self.planned_survey_date < today:
            stages.append("Vistoria")
        if self.planned_report_date and not self.actual_report_date and self.planned_report_date < today:
            stages.append("Laudo")
        return " e ".join(stages)

    @property
    def alert_stage(self):
        from django.utils import timezone
        today = timezone.localdate()
        three_days = today + timezone.timedelta(days=3)
        stages = []
        if self.planned_survey_date and not self.actual_survey_date and today <= self.planned_survey_date <= three_days:
            stages.append("Vistoria")
        if self.planned_report_date and not self.actual_report_date and today <= self.planned_report_date <= three_days:
            stages.append("Laudo")
        return " e ".join(stages)

    @property
    def is_survey_overdue(self):
        from django.utils import timezone
        today = timezone.localdate()
        return bool(self.planned_survey_date and not self.actual_survey_date and self.planned_survey_date < today)

    @property
    def is_survey_alert(self):
        from django.utils import timezone
        today = timezone.localdate()
        three_days = today + timezone.timedelta(days=3)
        return bool(self.planned_survey_date and not self.actual_survey_date and today <= self.planned_survey_date <= three_days)

    @property
    def is_report_overdue(self):
        from django.utils import timezone
        today = timezone.localdate()
        return bool(self.planned_report_date and not self.actual_report_date and self.planned_report_date < today)

    @property
    def is_report_alert(self):
        from django.utils import timezone
        today = timezone.localdate()
        three_days = today + timezone.timedelta(days=3)
        return bool(self.planned_report_date and not self.actual_report_date and today <= self.planned_report_date <= three_days)

    SCOPE_STAGES = {
        'LAUDOS': ['Acionamento Parceiro', 'Acesso', 'Vistoria', 'Laudo', 'Projeto Reforço'],
        'INSTALACAO': ['Acesso', 'Vistoria', 'QRF', 'WarRoom', 'PPI', 'Execução', 'ARQ'],
        'INFRA': ['Acesso', 'Vistoria', 'Projeto', 'Execução', 'RFI'],
        'FABRICA': ['Acesso', 'Vistoria', 'Projeto']
    }

    def get_stages_config(self):
        return self.SCOPE_STAGES.get(self.scope_type, self.SCOPE_STAGES['LAUDOS'])

    def sync_stages(self):
        """Sincroniza o campo JSON stages_status com base nos campos de banco legados."""
        stages = self.get_stages_config()
        if not self.stages_status:
            self.stages_status = {}
            
        new_status = {}
        for s in stages:
            if s in self.stages_status:
                new_status[s] = self.stages_status[s]
            else:
                new_status[s] = {'status': 'PENDING', 'date': None}
                
        # 1. Acesso
        if 'Acesso' in new_status:
            if self.access_status == self.AccessStatus.RELEASED:
                new_status['Acesso'] = {
                    'status': 'DONE',
                    'date': self.access_released_date.isoformat() if self.access_released_date else None
                }
            elif self.access_status == self.AccessStatus.NOT_REQUIRED:
                new_status['Acesso'] = {'status': 'SKIPPED', 'date': None}
            elif self.access_status == self.AccessStatus.NOT_STARTED:
                if new_status['Acesso'].get('status') in ['DONE', 'SKIPPED']:
                    new_status['Acesso'] = {'status': 'PENDING', 'date': None}
                    
        # 2. Vistoria
        if 'Vistoria' in new_status:
            if self.actual_survey_date:
                new_status['Vistoria'] = {
                    'status': 'DONE',
                    'date': self.actual_survey_date.isoformat() if self.actual_survey_date else None
                }
            else:
                if new_status['Vistoria'].get('status') == 'DONE':
                    new_status['Vistoria'] = {'status': 'PENDING', 'date': None}
                    
        # 3. Laudo
        if 'Laudo' in new_status:
            if self.actual_report_date:
                new_status['Laudo'] = {
                    'status': 'DONE',
                    'date': self.actual_report_date.isoformat() if self.actual_report_date else None
                }
            else:
                if new_status['Laudo'].get('status') == 'DONE':
                    new_status['Laudo'] = {'status': 'PENDING', 'date': None}
                    
        # 4. Projeto
        if 'Projeto' in new_status:
            if self.actual_report_date:
                new_status['Projeto'] = {
                    'status': 'DONE',
                    'date': self.actual_report_date.isoformat() if self.actual_report_date else None
                }
            else:
                if new_status['Projeto'].get('status') == 'DONE':
                    new_status['Projeto'] = {'status': 'PENDING', 'date': None}
                    
        self.stages_status = new_status

    def sync_to_legacy_fields(self):
        """Sincroniza os campos legados de banco com base no JSON stages_status."""
        if not self.stages_status:
            return
            
        from django.utils.dateparse import parse_date
        
        # 1. Acesso
        if 'Acesso' in self.stages_status:
            st = self.stages_status['Acesso'].get('status', 'PENDING')
            dt_str = self.stages_status['Acesso'].get('date')
            dt = parse_date(dt_str) if dt_str else None
            
            if st == 'DONE':
                self.access_status = self.AccessStatus.RELEASED
                if dt:
                    self.access_released_date = dt
            elif st == 'SKIPPED':
                self.access_status = self.AccessStatus.NOT_REQUIRED
                self.access_released_date = None
                self.access_requested_date = None
            else:
                if self.access_status not in [self.AccessStatus.REQUESTED, self.AccessStatus.NOT_STARTED]:
                    self.access_status = self.AccessStatus.NOT_STARTED
                    self.access_released_date = None
                    self.access_requested_date = None
                    
        # 2. Vistoria
        if 'Vistoria' in self.stages_status:
            st = self.stages_status['Vistoria'].get('status', 'PENDING')
            dt_str = self.stages_status['Vistoria'].get('date')
            dt = parse_date(dt_str) if dt_str else None
            
            if st == 'DONE':
                self.actual_survey_date = dt
            elif st == 'SKIPPED':
                self.actual_survey_date = None
            else:
                self.actual_survey_date = None
                
        # 3. Laudo
        if 'Laudo' in self.stages_status:
            st = self.stages_status['Laudo'].get('status', 'PENDING')
            dt_str = self.stages_status['Laudo'].get('date')
            dt = parse_date(dt_str) if dt_str else None
            
            if st == 'DONE':
                self.actual_report_date = dt
            elif st == 'SKIPPED':
                self.actual_report_date = None
            else:
                self.actual_report_date = None
                
        # 4. Projeto
        if 'Projeto' in self.stages_status:
            st = self.stages_status['Projeto'].get('status', 'PENDING')
            dt_str = self.stages_status['Projeto'].get('date')
            dt = parse_date(dt_str) if dt_str else None
            
            if st == 'DONE':
                self.actual_report_date = dt
            elif st == 'SKIPPED':
                self.actual_report_date = None
            else:
                self.actual_report_date = None

    def recalculate_status(self):
        from django.utils import timezone
        today = timezone.localdate()
        
        stages = self.get_stages_config()
        if stages:
            final_stage = stages[-1]
            final_status = self.stages_status.get(final_stage, {}).get('status', 'PENDING')
            if final_status in ['DONE', 'SKIPPED']:
                return self.SiteStatus.ACTIVE
        
        if (self.planned_survey_date and self.planned_survey_date < today and not self.actual_survey_date) or \
           (self.planned_report_date and self.planned_report_date < today and not self.actual_report_date):
            return self.SiteStatus.INACTIVE
            
        if (not self.actual_survey_date and not self.planned_survey_date) or \
           (not self.actual_report_date and not self.planned_report_date):
            return self.SiteStatus.MAINTENANCE
            
        if (self.planned_survey_date and today <= self.planned_survey_date <= today + timezone.timedelta(days=3) and not self.actual_survey_date) or \
           (self.planned_report_date and today <= self.planned_report_date <= today + timezone.timedelta(days=3) and not self.actual_report_date):
            return self.SiteStatus.MAINTENANCE
            
        return self.SiteStatus.PLANNED

    def save(self, *args, **kwargs):
        from django.utils.dateparse import parse_date
        
        # Garante que as datas sejam objetos datetime.date se forem strings
        for field in ['planned_survey_date', 'actual_survey_date', 'planned_report_date', 'actual_report_date', 'access_requested_date', 'access_released_date']:
            val = getattr(self, field)
            if isinstance(val, str):
                setattr(self, field, parse_date(val) if val else None)
        


        # Sincroniza stages_status com os campos legados se for uma alteração nos campos legados
        self.sync_stages()

        self.status = self.recalculate_status()
        super().save(*args, **kwargs)



# --- 3. REPOSITÓRIO DE ARQUIVOS POR SITE ---
def site_file_upload_path(instance, filename):
    # Organiza os arquivos na pasta física do site e categoria
    return f"sites/{instance.site.site_id}/{instance.category.lower()}/{filename}"

class SiteFile(models.Model):
    class FileCategory(models.TextChoices):
        PDF = 'PDF', 'Relatório Técnico (PDF)'
        IMAGE = 'IMAGE', 'Foto / Imagem (JPG/PNG)'
        DWG = 'DWG', 'Planta AutoCAD (DWG)'
        OTHER = 'OTHER', 'Outros Documentos'

    site = models.ForeignKey(
        Site, 
        on_delete=models.CASCADE, 
        related_name='files', 
        verbose_name="Site Vinculado"
    )
    file = models.FileField(
        upload_to=site_file_upload_path, 
        verbose_name="Arquivo Original"
    )
    description = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="Descrição do Conteúdo"
    )
    category = models.CharField(
        max_length=10,
        choices=FileCategory.choices,
        verbose_name="Categoria do Arquivo"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Enviado por"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Data do Upload")

    class Meta:
        verbose_name = "Arquivo de Site"
        verbose_name_plural = "Arquivos de Sites"
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.site.site_id} - {self.get_category_display()} - {os.path.basename(self.file.name)}"

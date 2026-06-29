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

    profile_picture = models.FileField(
        upload_to="profile_pics/",
        null=True,
        blank=True,
        verbose_name="Foto de Perfil"
    )

    profile_picture_base64 = models.TextField(
        null=True,
        blank=True,
        verbose_name="Foto de Perfil (Base64)"
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

    class UF(models.TextChoices):
        AC = 'AC', 'Acre'
        AL = 'AL', 'Alagoas'
        AP = 'AP', 'Amapá'
        AM = 'AM', 'Amazonas'
        BA = 'BA', 'Bahia'
        CE = 'CE', 'Ceará'
        DF = 'DF', 'Distrito Federal'
        ES = 'ES', 'Espírito Santo'
        GO = 'GO', 'Goiás'
        MA = 'MA', 'Maranhão'
        MT = 'MT', 'Mato Grosso'
        MS = 'MS', 'Mato Grosso do Sul'
        MG = 'MG', 'Minas Gerais'
        PA = 'PA', 'Pará'
        PB = 'PB', 'Paraíba'
        PR = 'PR', 'Paraná'
        PE = 'PE', 'Pernambuco'
        PI = 'PI', 'Piauí'
        RJ = 'RJ', 'Rio de Janeiro'
        RN = 'RN', 'Rio Grande do Norte'
        RS = 'RS', 'Rio Grande do Sul'
        RO = 'RO', 'Rondônia'
        RR = 'RR', 'Roraima'
        SC = 'SC', 'Santa Catarina'
        SP = 'SP', 'São Paulo'
        SE = 'SE', 'Sergipe'
        TO = 'TO', 'Tocantins'

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
    uf = models.CharField(
        max_length=2,
        choices=UF.choices,
        blank=True,
        null=True,
        verbose_name="UF / Estado"
    )
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial_legacy_values = {
            'access_status': self.access_status,
            'access_released_date': self.access_released_date,
            'planned_survey_date': self.planned_survey_date,
            'actual_survey_date': self.actual_survey_date,
            'planned_report_date': self.planned_report_date,
            'actual_report_date': self.actual_report_date,
        }

    @property
    def days_overdue(self):
        from django.utils import timezone
        today = timezone.localdate()
        max_delay = 0
        for milestone in self.get_card_milestones():
            if milestone['is_overdue'] and milestone['planned_date']:
                delay = (today - milestone['planned_date']).days
                if delay > max_delay:
                    max_delay = delay
        return max_delay

    @property
    def overdue_stage(self):
        stages = [m['name'] for m in self.get_card_milestones() if m['is_overdue']]
        return " e ".join(stages)

    @property
    def alert_stage(self):
        stages = [m['name'] for m in self.get_card_milestones() if m['is_alert']]
        return " e ".join(stages)

    @property
    def is_planning_missing(self):
        return any(not m['is_completed'] and not m['planned_date'] for m in self.get_card_milestones())

    @property
    def current_stage_name(self):
        first_pending = self.stages.filter(status='PENDING').order_by('order').first()
        if first_pending:
            return first_pending.stage_name
        return "Finalizado"

    def get_merged_reschedule_history(self):
        """Retorna o histórico unificado de replanejamentos de todas as etapas."""
        from django.utils import timezone

        history_list = []
        now = timezone.now()

        # Lê de SiteStageReschedule (nova fonte de verdade)
        for reschedule in SiteStageReschedule.objects.filter(
            stage__site=self
        ).select_related('stage', 'created_by').order_by('-created_at'):
            history_list.append({
                'created_at': reschedule.created_at,
                'created_by_name': (
                    reschedule.created_by.get_full_name() or reschedule.created_by.username
                ) if reschedule.created_by else 'Sistema',
                'reason': reschedule.reason,
                'changes': [{
                    'stage_name': reschedule.stage.stage_name,
                    'previous_date': reschedule.previous_date,
                    'new_date': reschedule.new_date,
                }],
            })

        # Mantém compatibilidade com SiteRescheduleHistory legado (escopo LAUDOS antigo)
        for bh in self.reschedule_histories.all().select_related('created_by'):
            changes = []
            if bh.previous_planned_survey_date != bh.new_planned_survey_date:
                changes.append({
                    'stage_name': 'Vistoria',
                    'previous_date': bh.previous_planned_survey_date,
                    'new_date': bh.new_planned_survey_date,
                })
            if bh.previous_planned_report_date != bh.new_planned_report_date:
                label = 'Laudo' if self.scope_type == 'LAUDOS' else 'Projeto'
                changes.append({
                    'stage_name': label,
                    'previous_date': bh.previous_planned_report_date,
                    'new_date': bh.new_planned_report_date,
                })
            if changes:
                history_list.append({
                    'created_at': bh.created_at,
                    'created_by_name': (
                        bh.created_by.get_full_name() or bh.created_by.username
                    ) if bh.created_by else 'Sistema',
                    'reason': bh.reason,
                    'changes': changes,
                })

        def get_sort_key(item):
            dt = item['created_at']
            if dt is None:
                return now
            if timezone.is_naive(dt):
                return timezone.make_aware(dt)
            return dt

        history_list.sort(key=get_sort_key, reverse=True)
        return history_list

    def get_card_milestones(self):
        """Retorna as etapas do site para exibição nos cards, lendo de SiteStage."""
        import datetime
        from django.utils import timezone

        today = timezone.localdate()
        three_days_limit = today + datetime.timedelta(days=3)

        # Subconjunto de etapas visíveis no card (resumo)
        card_stages_map = {
            'INSTALACAO': ['Vistoria', 'QRF', 'WarRoom', 'PPI', 'ARQ'],
            'LAUDOS':     ['Vistoria', 'Laudo'],
            'INFRA':      ['Vistoria', 'Projeto', 'Execução', 'RFI'],
            'FABRICA':    ['Vistoria', 'Projeto'],
        }
        card_stage_names = card_stages_map.get(self.scope_type, self.get_stages_config())

        icon_map = {
            'Vistoria': 'eye', 'Laudo': 'file-text', 'Projeto': 'file-text',
            'QRF': 'clipboard-list', 'WarRoom': 'users', 'PPI': 'check-square',
            'Execução': 'play', 'Execução Rollout': 'play', 'RFI': 'help-circle',
            'ARQ': 'archive', 'Acionamento Parceiro': 'user-plus', 'Acesso': 'key',
        }

        # Busca todas as SiteStage deste site em uma só query
        stage_objs = {s.stage_name: s for s in self.stages.all()}

        milestones = []
        for name in card_stage_names:
            stage = stage_objs.get(name)
            if stage:
                status = stage.status
                planned_date = stage.planned_date
                actual_date = stage.actual_date
            else:
                status = 'PENDING'
                planned_date = None
                actual_date = None

            is_completed = status in ('DONE', 'SKIPPED') or actual_date is not None
            is_overdue = False
            is_alert = False

            if not is_completed and planned_date:
                if planned_date < today:
                    is_overdue = True
                elif today <= planned_date <= three_days_limit:
                    is_alert = True

            milestones.append({
                'name': name,
                'icon': icon_map.get(name, 'check'),
                'planned_date': planned_date,
                'actual_date': actual_date,
                'status': status,
                'is_completed': is_completed,
                'is_overdue': is_overdue,
                'is_alert': is_alert,
            })

        return milestones


    @property
    def is_survey_overdue(self):
        from django.utils import timezone
        today = timezone.localdate()
        return bool(self.planned_survey_date and not self.actual_survey_date and self.planned_survey_date < today)

    @property
    def is_survey_due(self):
        from django.utils import timezone
        today = timezone.localdate()
        return bool(self.planned_survey_date and not self.actual_survey_date and self.planned_survey_date <= today)

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
    def is_report_due(self):
        from django.utils import timezone
        today = timezone.localdate()
        return bool(self.planned_report_date and not self.actual_report_date and self.planned_report_date <= today)

    @property
    def is_report_alert(self):
        from django.utils import timezone
        today = timezone.localdate()
        three_days = today + timezone.timedelta(days=3)
        return bool(self.planned_report_date and not self.actual_report_date and today <= self.planned_report_date <= three_days)

    @property
    def access_lead_time(self):
        if self.access_requested_date and self.access_released_date:
            return (self.access_released_date - self.access_requested_date).days
        return None

    @property
    def current_responsible_sector(self):
        if self.scope_type != 'INSTALACAO':
            return None
        # Get statuses from SiteStage
        stages = {s.stage_name: s.status for s in self.stages.all()}
        ppi_status = stages.get('PPI', 'PENDING')
        exec_status = stages.get('Execução Rollout', 'PENDING')
        arq_status = stages.get('ARQ', 'PENDING')
        
        if ppi_status != 'DONE':
            return "Engenharia"
        elif exec_status != 'DONE':
            return "Rollout"
        elif arq_status != 'DONE':
            return "Engenharia"
        else:
            return "Finalizado"

    SCOPE_STAGES = {
        'LAUDOS': ['Acionamento Parceiro', 'Acesso', 'Vistoria', 'Laudo'],
        'INSTALACAO': ['Acesso', 'Vistoria', 'QRF', 'WarRoom', 'PPI', 'Execução Rollout', 'ARQ'],
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
        
        # Migração defensiva de "Execução" para "Execução Rollout"
        if self.scope_type == 'INSTALACAO' and 'Execução' in self.stages_status and 'Execução Rollout' not in self.stages_status:
            self.stages_status['Execução Rollout'] = self.stages_status['Execução']

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

        # Site ainda não tem PK: sem etapas no banco, retorna PLANNED
        if not self.pk:
            return self.SiteStatus.PLANNED

        # Verifica se a etapa final do escopo foi concluída
        stages = self.get_stages_config()
        if stages:
            final_name = stages[-1]
            final_stage = self.stages.filter(stage_name=final_name).first()
            if final_stage and final_stage.status in ('DONE', 'SKIPPED'):
                return self.SiteStatus.ACTIVE

        milestones = self.get_card_milestones()

        # INACTIVE: qualquer marco vencido e não concluído
        if any(m['is_overdue'] for m in milestones):
            return self.SiteStatus.INACTIVE

        # MAINTENANCE: sem data planejada ou dentro do alerta de 3 dias
        if any((not m['is_completed'] and not m['planned_date']) or m['is_alert'] for m in milestones):
            return self.SiteStatus.MAINTENANCE

        return self.SiteStatus.PLANNED

    def ensure_stages_exist(self):
        """Garante que todas as SiteStage do escopo atual existam no banco."""
        existing = set(self.stages.values_list('stage_name', flat=True))
        for order, name in enumerate(self.get_stages_config(), 1):
            if name not in existing:
                SiteStage.objects.create(
                    site=self,
                    scope_type=self.scope_type,
                    stage_name=name,
                    order=order,
                )

    def sync_legacy_fields_to_stages(self, only_fields=None):
        """Sincroniza os campos legados do Site para as instâncias de SiteStage correspondentes."""
        if not self.pk:
            return

        if getattr(self, '_syncing_stages', False):
            return

        self._syncing_stages = True
        try:
            self.ensure_stages_exist()

            # 1. Acesso
            if only_fields is None or 'access_status' in only_fields or 'access_released_date' in only_fields:
                acesso = self.stages.filter(stage_name='Acesso').first()
                if acesso:
                    new_status = 'PENDING'
                    new_actual_date = None
                    if self.access_status == self.AccessStatus.RELEASED:
                        new_status = 'DONE'
                        new_actual_date = self.access_released_date
                    elif self.access_status == self.AccessStatus.NOT_REQUIRED:
                        new_status = 'SKIPPED'

                    if acesso.status != new_status or acesso.actual_date != new_actual_date:
                        acesso.status = new_status
                        acesso.actual_date = new_actual_date
                        acesso.save()

            # 2. Vistoria
            if only_fields is None or 'planned_survey_date' in only_fields or 'actual_survey_date' in only_fields:
                vistoria = self.stages.filter(stage_name='Vistoria').first()
                if vistoria:
                    new_status = vistoria.status
                    new_actual_date = vistoria.actual_date
                    if self.actual_survey_date:
                        new_status = 'DONE'
                        new_actual_date = self.actual_survey_date
                    else:
                        if vistoria.status == 'DONE':
                            new_status = 'PENDING'
                        new_actual_date = None

                    if (vistoria.planned_date != self.planned_survey_date or 
                        vistoria.status != new_status or 
                        vistoria.actual_date != new_actual_date):
                        vistoria.planned_date = self.planned_survey_date
                        vistoria.status = new_status
                        vistoria.actual_date = new_actual_date
                        vistoria.save()

            # 3. Laudo ou Projeto
            if only_fields is None or 'planned_report_date' in only_fields or 'actual_report_date' in only_fields:
                report_name = 'Laudo' if self.scope_type == 'LAUDOS' else 'Projeto'
                report_stage = self.stages.filter(stage_name=report_name).first()
                if report_stage:
                    new_status = report_stage.status
                    new_actual_date = report_stage.actual_date
                    if self.actual_report_date:
                        new_status = 'DONE'
                        new_actual_date = self.actual_report_date
                    else:
                        if report_stage.status == 'DONE':
                            new_status = 'PENDING'
                        new_actual_date = None

                    if (report_stage.planned_date != self.planned_report_date or 
                        report_stage.status != new_status or 
                        report_stage.actual_date != new_actual_date):
                        report_stage.planned_date = self.planned_report_date
                        report_stage.status = new_status
                        report_stage.actual_date = new_actual_date
                        report_stage.save()
        finally:
            self._syncing_stages = False

    def save(self, *args, **kwargs):
        if getattr(self, '_syncing_stages', False):
            super().save(*args, **kwargs)
            return

        self._saving_site = True
        try:
            from django.utils.dateparse import parse_date

            # Garante que as datas legadas sejam objetos datetime.date se chegarem como strings
            for field in ['planned_survey_date', 'actual_survey_date', 'planned_report_date',
                          'actual_report_date', 'access_requested_date', 'access_released_date']:
                val = getattr(self, field)
                if isinstance(val, str):
                    setattr(self, field, parse_date(val) if val else None)

            is_new = self.pk is None
            
            # Captura status anterior se não for novo
            old_status = None
            if not is_new:
                old_status = type(self).objects.filter(pk=self.pk).values_list('status', flat=True).first()

            self.status = self.recalculate_status()  # PLANNED para site novo (sem PK ainda)
            super().save(*args, **kwargs)

            if is_new:
                # Cria as SiteStage e recalcula o status com as etapas já no banco
                self.ensure_stages_exist()
                self.sync_legacy_fields_to_stages()
                new_status = self.recalculate_status()
                if new_status != self.status:
                    self.status = new_status
                    type(self).objects.filter(pk=self.pk).update(status=new_status)
                # Inicializa os valores legados iniciais no novo objeto
                self._initial_legacy_values = {
                    'access_status': self.access_status,
                    'access_released_date': self.access_released_date,
                    'planned_survey_date': self.planned_survey_date,
                    'actual_survey_date': self.actual_survey_date,
                    'planned_report_date': self.planned_report_date,
                    'actual_report_date': self.actual_report_date,
                }
                
                # Dispara notificação de integração de novo site
                try:
                    user_name = "Sistema"
                    if hasattr(self, 'modified_by') and self.modified_by:
                        user_name = self.modified_by.first_name or self.modified_by.username

                    Notification.create_notification(
                        site=self,
                        title=f"Novo Site Cadastrado: {self.name}",
                        message=f"O site {self.name} foi integrado no escopo {self.get_scope_type_display()} por {user_name}.",
                        notification_type=Notification.NotificationType.INFO
                    )
                except Exception as e:
                    pass
            else:
                # Se não for novo, sincroniza apenas os campos legados alterados em memória
                changed_fields = {}
                initial_vals = getattr(self, '_initial_legacy_values', {})
                for field in ['access_status', 'access_released_date', 'planned_survey_date',
                              'actual_survey_date', 'planned_report_date', 'actual_report_date']:
                    val = initial_vals.get(field)
                    if getattr(self, field) != val:
                        changed_fields[field] = getattr(self, field)
                
                if changed_fields:
                    self.sync_legacy_fields_to_stages(only_fields=changed_fields.keys())
                    initial_vals.update(changed_fields)
                
                # Dispara notificações de mudança de status
                try:
                    new_status = self.status
                    if old_status and old_status != new_status:
                        user_name = "Sistema"
                        if hasattr(self, 'modified_by') and self.modified_by:
                            user_name = self.modified_by.first_name or self.modified_by.username

                        if new_status == self.SiteStatus.MAINTENANCE:
                            Notification.create_notification(
                                site=self,
                                title=f"Site em Alerta: {self.name}",
                                message=f"O site {self.name} entrou em estado 'Em Alerta' no monitoramento NOC por {user_name}.",
                                notification_type=Notification.NotificationType.ALERT
                            )
                        elif new_status == self.SiteStatus.INACTIVE:
                            Notification.create_notification(
                                site=self,
                                title=f"Prazo Vencido: {self.name}",
                                message=f"O site {self.name} entrou em estado 'Prazo Vencido' por {user_name}.",
                                notification_type=Notification.NotificationType.ALERT
                            )
                except Exception as e:
                    pass
        finally:
            self._saving_site = False


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


class SiteRescheduleHistory(models.Model):
    """Legado: usado para Laudos antes da migração para SiteStageReschedule."""
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name='reschedule_histories',
        verbose_name="Site"
    )
    previous_planned_survey_date = models.DateField(blank=True, null=True, verbose_name="Vistoria Planejada Anterior")
    new_planned_survey_date = models.DateField(blank=True, null=True, verbose_name="Nova Vistoria Planejada")
    previous_planned_report_date = models.DateField(blank=True, null=True, verbose_name="Laudo Planejado Anterior")
    new_planned_report_date = models.DateField(blank=True, null=True, verbose_name="Novo Laudo Planejado")
    reason = models.TextField(blank=True, null=True, verbose_name="Motivo do Replanejamento")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Registrado em")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Registrado por"
    )

    class Meta:
        verbose_name = "Histórico de Replanejamento (Legado)"
        verbose_name_plural = "Históricos de Replanejamento (Legado)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.site.name} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"


# --- 5. ETAPAS POR SITE (Opção C — fonte de verdade relacional) ---
class SiteStage(models.Model):
    """Uma linha por etapa por site. Substitui o campo JSON stages_status."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendente'
        DONE    = 'DONE',    'Concluído'
        SKIPPED = 'SKIPPED', 'Ignorado'

    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name='stages',
        verbose_name="Site"
    )
    scope_type = models.CharField(
        max_length=20,
        choices=Site.ScopeType.choices,
        verbose_name="Escopo"
    )
    stage_name = models.CharField(max_length=100, verbose_name="Nome da Etapa")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    planned_date = models.DateField(blank=True, null=True, verbose_name="Data Planejada")
    actual_date  = models.DateField(blank=True, null=True, verbose_name="Data Realizada")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Status"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Observações")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('site', 'stage_name')]
        ordering = ['site', 'order']
        verbose_name = "Etapa do Site"
        verbose_name_plural = "Etapas dos Sites"

    def __str__(self):
        return f"{self.site.site_id} | {self.stage_name} ({self.status})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Sincroniza de volta com os campos legados do site correspondente
        site = self.site
        if getattr(site, '_syncing_stages', False) or getattr(site, '_saving_site', False):
            return

        updated_fields = set()
        if self.stage_name == 'Acesso':
            if self.status == self.Status.DONE:
                if site.access_status != site.AccessStatus.RELEASED or site.access_released_date != self.actual_date:
                    site.access_status = site.AccessStatus.RELEASED
                    site.access_released_date = self.actual_date
                    updated_fields.update(['access_status', 'access_released_date'])
            elif self.status == self.Status.SKIPPED:
                if site.access_status != site.AccessStatus.NOT_REQUIRED:
                    site.access_status = site.AccessStatus.NOT_REQUIRED
                    site.access_released_date = None
                    updated_fields.update(['access_status', 'access_released_date'])
            else:
                if site.access_status not in [site.AccessStatus.NOT_STARTED, site.AccessStatus.REQUESTED]:
                    site.access_status = site.AccessStatus.NOT_STARTED
                    site.access_released_date = None
                    updated_fields.update(['access_status', 'access_released_date'])
        elif self.stage_name == 'Vistoria':
            if site.planned_survey_date != self.planned_date:
                site.planned_survey_date = self.planned_date
                updated_fields.add('planned_survey_date')
            if self.status == self.Status.DONE:
                if site.actual_survey_date != self.actual_date:
                    site.actual_survey_date = self.actual_date
                    updated_fields.add('actual_survey_date')
            else:
                if site.actual_survey_date is not None:
                    site.actual_survey_date = None
                    updated_fields.add('actual_survey_date')
        elif self.stage_name in ('Laudo', 'Projeto'):
            if site.planned_report_date != self.planned_date:
                site.planned_report_date = self.planned_date
                updated_fields.add('planned_report_date')
            if self.status == self.Status.DONE:
                if site.actual_report_date != self.actual_date:
                    site.actual_report_date = self.actual_date
                    updated_fields.add('actual_report_date')
            else:
                if site.actual_report_date is not None:
                    site.actual_report_date = None
                    updated_fields.add('actual_report_date')

        if updated_fields:
            site._syncing_stages = True
            try:
                site.save(update_fields=list(updated_fields))
            finally:
                site._syncing_stages = False


class SiteStageReschedule(models.Model):
    """Histórico de replanejamento por etapa (SiteStage). Substitui reschedule_history do JSON."""

    stage = models.ForeignKey(
        SiteStage,
        on_delete=models.CASCADE,
        related_name='reschedules',
        verbose_name="Etapa"
    )
    previous_date = models.DateField(blank=True, null=True, verbose_name="Data Anterior")
    new_date      = models.DateField(blank=True, null=True, verbose_name="Nova Data")
    reason        = models.TextField(blank=True, null=True, verbose_name="Motivo")
    created_at    = models.DateTimeField(auto_now_add=True, verbose_name="Registrado em")
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Registrado por"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Replanejamento de Etapa"
        verbose_name_plural = "Replanejamentos de Etapas"

    def __str__(self):
        return f"{self.stage} — {self.previous_date} → {self.new_date}"


class CalendarNote(models.Model):
    date = models.DateField(verbose_name="Data")
    title = models.CharField(max_length=200, verbose_name="Título")
    description = models.TextField(blank=True, null=True, verbose_name="Anotação")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Nota do Calendário"
        verbose_name_plural = "Notas do Calendário"
        ordering = ['date', 'created_at']

    def __str__(self):
        return f"{self.date} - {self.title}"


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        INFO = 'INFO', 'Informativo'
        ALERT = 'ALERT', 'Alerta / Atraso'
        UPLOAD = 'UPLOAD', 'Upload de Arquivo'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Usuário"
    )
    title = models.CharField(max_length=200, verbose_name="Título")
    message = models.TextField(verbose_name="Mensagem")
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.INFO,
        verbose_name="Tipo de Notificação"
    )
    site = models.ForeignKey(
        'Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name="Site Relacionado"
    )
    is_read = models.BooleanField(default=False, verbose_name="Lida")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"

    def __str__(self):
        return f"{self.user.username} - {self.title} ({'Lida' if self.is_read else 'Não Lida'})"

    @classmethod
    def create_notification(cls, site, title, message, notification_type):
        # Seleciona todos os administradores e engenheiros
        recipients = User.objects.filter(role__in=[User.Role.ADMIN, User.Role.ENGINEER])
        notifications = [
            cls(
                user=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                site=site
            )
            for recipient in recipients
        ]
        if notifications:
            cls.objects.bulk_create(notifications)



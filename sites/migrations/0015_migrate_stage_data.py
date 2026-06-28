"""
Data migration: populates SiteStage from existing stages_status JSON and legacy date fields.
"""
from django.db import migrations
from django.utils.dateparse import parse_date


SCOPE_STAGES = {
    'LAUDOS':     ['Acionamento Parceiro', 'Acesso', 'Vistoria', 'Laudo'],
    'INSTALACAO': ['Acesso', 'Vistoria', 'QRF', 'WarRoom', 'PPI', 'Execução Rollout', 'ARQ'],
    'INFRA':      ['Acesso', 'Vistoria', 'Projeto', 'Execução', 'RFI'],
    'FABRICA':    ['Acesso', 'Vistoria', 'Projeto'],
}


def to_date(val):
    if not val:
        return None
    if hasattr(val, 'year'):
        return val
    if isinstance(val, str):
        return parse_date(val)
    return None


def migrate_stages_forward(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    SiteStage = apps.get_model('sites', 'SiteStage')
    SiteStageReschedule = apps.get_model('sites', 'SiteStageReschedule')
    SiteRescheduleHistory = apps.get_model('sites', 'SiteRescheduleHistory')

    for site in Site.objects.all():
        scope = site.scope_type or 'LAUDOS'
        stage_names = SCOPE_STAGES.get(scope, SCOPE_STAGES['LAUDOS'])
        stages_json = site.stages_status or {}

        # Defensive: normalize "Execução" → "Execução Rollout" for INSTALACAO
        if scope == 'INSTALACAO' and 'Execução' in stages_json and 'Execução Rollout' not in stages_json:
            stages_json['Execução Rollout'] = stages_json.pop('Execução')

        for order, name in enumerate(stage_names, 1):
            # --- Determine planned_date, actual_date, status from legacy fields or JSON ---
            planned_date = None
            actual_date = None
            status = 'PENDING'

            if name == 'Vistoria':
                planned_date = site.planned_survey_date
                actual_date  = site.actual_survey_date
                if actual_date:
                    status = 'DONE'

            elif name in ('Laudo', 'Projeto'):
                planned_date = site.planned_report_date
                actual_date  = site.actual_report_date
                if actual_date:
                    status = 'DONE'

            elif name == 'Acesso':
                access = site.access_status or 'NOT_STARTED'
                if access == 'RELEASED':
                    status = 'DONE'
                    actual_date = site.access_released_date
                elif access == 'NOT_REQUIRED':
                    status = 'SKIPPED'
                else:
                    status = 'PENDING'

            else:
                # Read from JSON
                info = stages_json.get(name, {})
                raw_status = info.get('status', 'PENDING')
                status = raw_status if raw_status in ('PENDING', 'DONE', 'SKIPPED') else 'PENDING'
                planned_date = to_date(info.get('planned_date'))
                actual_date  = to_date(info.get('date') if raw_status == 'DONE' else None)

            stage_obj, _ = SiteStage.objects.get_or_create(
                site=site,
                stage_name=name,
                defaults={
                    'scope_type':   scope,
                    'order':        order,
                    'planned_date': planned_date,
                    'actual_date':  actual_date,
                    'status':       status,
                },
            )

            # --- Migrate reschedule history from JSON ---
            if name not in ('Vistoria', 'Laudo', 'Projeto', 'Acesso'):
                info = stages_json.get(name, {})
                for entry in info.get('reschedule_history', []):
                    SiteStageReschedule.objects.create(
                        stage=stage_obj,
                        previous_date=to_date(entry.get('previous_date')),
                        new_date=to_date(entry.get('new_date')),
                        reason=entry.get('reason'),
                    )

        # --- Migrate SiteRescheduleHistory (Laudos legacy) into SiteStageReschedule ---
        for bh in SiteRescheduleHistory.objects.filter(site=site):
            # Vistoria
            if bh.previous_planned_survey_date != bh.new_planned_survey_date:
                try:
                    vistoria_stage = SiteStage.objects.get(site=site, stage_name='Vistoria')
                    SiteStageReschedule.objects.create(
                        stage=vistoria_stage,
                        previous_date=bh.previous_planned_survey_date,
                        new_date=bh.new_planned_survey_date,
                        reason=bh.reason,
                        created_by=bh.created_by,
                    )
                except SiteStage.DoesNotExist:
                    pass

            # Laudo / Projeto
            label = 'Laudo' if scope == 'LAUDOS' else 'Projeto'
            if bh.previous_planned_report_date != bh.new_planned_report_date:
                try:
                    laudo_stage = SiteStage.objects.get(site=site, stage_name=label)
                    SiteStageReschedule.objects.create(
                        stage=laudo_stage,
                        previous_date=bh.previous_planned_report_date,
                        new_date=bh.new_planned_report_date,
                        reason=bh.reason,
                        created_by=bh.created_by,
                    )
                except SiteStage.DoesNotExist:
                    pass


def migrate_stages_backward(apps, schema_editor):
    # Rollback: just delete all SiteStage rows
    SiteStage = apps.get_model('sites', 'SiteStage')
    SiteStage.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0014_sitestage_sitestagereschedule'),
    ]

    operations = [
        migrations.RunPython(
            migrate_stages_forward,
            migrate_stages_backward,
        ),
    ]

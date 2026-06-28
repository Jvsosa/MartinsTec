import os
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponseForbidden
from .models import Site, SiteFile, User, SiteRescheduleHistory, SiteStage, SiteStageReschedule
from django.db import IntegrityError
from django.utils.dateparse import parse_date

# --- VIEW DE LOGIN ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('site_list')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Bem-vindo de volta, {user.first_name or user.username}!")
            return redirect('site_list')
        else:
            messages.error(request, "Usuário ou senha inválidos.")
            
    return render(request, 'login.html')


# --- VIEW DE LOGOUT ---
def logout_view(request):
    logout(request)
    messages.info(request, "Você encerrou a sessão.")
    return redirect('login')


# --- LISTAGEM DE SITES DE TELECOM ---
@login_required
def site_list(request):
    # Recalcula e atualiza o status de todos os sites com base nos prazos versus data atual
    from django.utils import timezone
    today = timezone.localdate()
    
    for site in Site.objects.all():
        old_status = site.status
        new_status = site.recalculate_status()
        if old_status != new_status:
            site.status = new_status
            site.save(update_fields=['status'])

    # Processa criação de novo site se for POST e o usuário tiver permissão (Admin ou Engenheiro)
    if request.method == 'POST':
        if request.user.role not in [User.Role.ADMIN, User.Role.ENGINEER]:
            messages.error(request, "Seu cargo não possui permissão para cadastrar sites.")
            return redirect('site_list')

        site_id_raw = request.POST.get('site_id', '').strip().upper()
        site_id = site_id_raw if site_id_raw else None
        name = request.POST.get('name').strip()
        address = request.POST.get('address', '').strip() or None
        uf = request.POST.get('uf', '').strip() or None
        latitude_str = request.POST.get('latitude', '').strip() or None
        longitude_str = request.POST.get('longitude', '').strip() or None
        scope_type = request.POST.get('scope_type')
        partner_company = request.POST.get('partner_company', '').strip() or None
        site_type = request.POST.get('site_type', Site.SiteType.ROOFTOP)
        operator = request.POST.get('operator', '').strip() or None
        
        p_survey = request.POST.get('planned_survey_date')
        planned_survey_date = parse_date(p_survey) if p_survey else None
        
        p_report = request.POST.get('planned_report_date')
        planned_report_date = parse_date(p_report) if p_report else None
        
        description = request.POST.get('description')
 
        try:
            new_site = Site.objects.create(
                site_id=site_id,
                name=name,
                address=address,
                uf=uf,
                latitude=latitude_str,
                longitude=longitude_str,
                scope_type=scope_type,
                partner_company=partner_company,
                site_type=site_type,
                operator=operator,
                planned_survey_date=planned_survey_date,
                planned_report_date=planned_report_date,
                description=description
            )
            messages.success(request, f"Site {new_site.site_id or new_site.name} cadastrado com sucesso!")
        except IntegrityError:
            messages.error(request, f"Erro: O ID do Site '{site_id}' já está cadastrado.")
        except Exception as e:
            messages.error(request, f"Erro ao salvar o site: {str(e)}")

        return redirect('site_list')

    # Filtragem de busca simples e status
    from django.db.models import Q
    from django.core.paginator import Paginator

    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'ALL').strip()

    sites_qs = Site.objects.all()

    if status_filter and status_filter != 'ALL':
        sites_qs = sites_qs.filter(status=status_filter)

    if query:
        sites_qs = sites_qs.filter(
            Q(site_id__icontains=query) |
            Q(name__icontains=query) |
            Q(operator__icontains=query)
        )

    # Paginação (24 sites por página)
    paginator = Paginator(sites_qs, 24)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Se for requisição AJAX para scroll infinito, retorna apenas o bloco de cards
    if request.GET.get('ajax') == '1':
        return render(request, 'sites/partials/_site_cards.html', {'sites': page_obj})

    sites = page_obj

    # Cálculo dos contadores (KPIs) para o topo do painel
    total_sites = Site.objects.count()
    active_sites = Site.objects.filter(status=Site.SiteStatus.ACTIVE).count()
    maintenance_sites = Site.objects.filter(status=Site.SiteStatus.MAINTENANCE).count()
    planned_sites = Site.objects.filter(status=Site.SiteStatus.PLANNED).count()
    inactive_sites = Site.objects.filter(status=Site.SiteStatus.INACTIVE).count()
    total_files = SiteFile.objects.count()

    # Listas para o dashboard de prazos
    overdue_list = Site.objects.filter(status=Site.SiteStatus.INACTIVE)
    alert_list = Site.objects.filter(status=Site.SiteStatus.MAINTENANCE)

    # Contagem de arquivos por categoria para gráficos
    pdf_files = SiteFile.objects.filter(category='PDF').count()
    image_files = SiteFile.objects.filter(category='IMAGE').count()
    dwg_files = SiteFile.objects.filter(category='DWG').count()
    other_files = SiteFile.objects.filter(category='OTHER').count()

    # Atividades recentes (Uploads)
    recent_activities = SiteFile.objects.select_related('site', 'uploaded_by').order_by('-uploaded_at')[:5]

    # --- CÁLCULO DE LEADTIME POR ESCOPO, ETAPA E PARCEIRO ---
    import json as _json

    all_sites = list(Site.objects.prefetch_related('stages').all())
    scope_configs = Site.SCOPE_STAGES  # {'LAUDOS': [...], 'INSTALACAO': [...], ...}

    # Estruturas de dados para coleta
    # scope_stage_times[scope][transition_label] = [dias, dias, ...]
    scope_stage_times = {}
    # partner_data[partner] = {scope: {transition: [dias], ...}, total_sites, finished_sites, total_times}
    partner_data = {}
    detailed_lead_times = []
    # scope_totals[scope] = [total_days, ...]  (ciclo completo)
    scope_totals = {}
    # Contadores por escopo
    scope_counts = {}

    for s in all_sites:
        scope = s.scope_type
        stages_config = scope_configs.get(scope, [])
        if not stages_config:
            continue

        creation_date = timezone.localdate(s.created_at)

        # Monta mapa de etapas do site: {stage_name: SiteStage}
        stage_objs = {st.stage_name: st for st in s.stages.all()}

        # Inicializa escopo se necessário
        if scope not in scope_stage_times:
            scope_stage_times[scope] = {}
            scope_totals[scope] = []
            scope_counts[scope] = {'total': 0, 'finished': 0}

        scope_counts[scope]['total'] += 1

        # Calcula leadtime entre etapas consecutivas
        site_transitions = []
        first_actual = None
        last_actual = None

        for i, stage_name in enumerate(stages_config):
            stage_obj = stage_objs.get(stage_name)
            actual = stage_obj.actual_date if stage_obj else None

            if i == 0 and actual and first_actual is None:
                first_actual = actual
            if actual:
                last_actual = actual

            # Calcula transição: etapa anterior → etapa atual
            if i == 0:
                # Primeira etapa: Acionamento (created_at) → Etapa
                prev_date = creation_date
                prev_name = 'Acionamento'
            else:
                prev_stage_name = stages_config[i - 1]
                prev_obj = stage_objs.get(prev_stage_name)
                prev_date = prev_obj.actual_date if prev_obj else None
                prev_name = prev_stage_name

            transition_label = f"{prev_name} → {stage_name}"
            days = None

            if prev_date and actual:
                days = max(0, (actual - prev_date).days)

                # Registra no escopo
                if transition_label not in scope_stage_times[scope]:
                    scope_stage_times[scope][transition_label] = []
                scope_stage_times[scope][transition_label].append(days)

                # Registra no parceiro
                partner = (s.partner_company or '').strip()
                if partner:
                    if partner not in partner_data:
                        partner_data[partner] = {
                            'total_sites': 0, 'finished_sites': 0,
                            'total_times': [], 'scopes': {},
                            'survey_times': [], 'report_times': []
                        }
                    if scope not in partner_data[partner]['scopes']:
                        partner_data[partner]['scopes'][scope] = {}
                    if transition_label not in partner_data[partner]['scopes'][scope]:
                        partner_data[partner]['scopes'][scope][transition_label] = []
                    partner_data[partner]['scopes'][scope][transition_label].append(days)

            site_transitions.append({
                'from': prev_name,
                'to': stage_name,
                'days': days,
                'display': f"{days} dias" if days is not None else ("Pendente" if not actual else "--"),
            })

        # Verifica se site é finalizado (última etapa concluída)
        last_stage_name = stages_config[-1]
        last_stage_obj = stage_objs.get(last_stage_name)
        is_finished = last_stage_obj and last_stage_obj.status in ('DONE', 'SKIPPED')

        if is_finished:
            scope_counts[scope]['finished'] += 1

        # Ciclo total
        total_days = None
        if last_actual:
            total_days = max(0, (last_actual - creation_date).days)
            scope_totals[scope].append(total_days)

        # Contabiliza parceiro
        partner = (s.partner_company or '').strip()
        if partner:
            if partner not in partner_data:
                partner_data[partner] = {
                    'total_sites': 0, 'finished_sites': 0,
                    'total_times': [], 'scopes': {},
                    'survey_times': [], 'report_times': []
                }
            partner_data[partner]['total_sites'] += 1
            if is_finished:
                partner_data[partner]['finished_sites'] += 1
            if total_days is not None:
                partner_data[partner]['total_times'].append(total_days)
            # Para compatibilidade com testes legados
            if s.actual_survey_date:
                sd = (s.actual_survey_date - creation_date).days
                partner_data[partner]['survey_times'].append(max(0, sd))
            if s.actual_survey_date and s.actual_report_date:
                rd = (s.actual_report_date - s.actual_survey_date).days
                partner_data[partner]['report_times'].append(max(0, rd))

        # Registro detalhado para tabela site-a-site
        current_stage = 'Finalizado'
        if not is_finished:
            for sn in stages_config:
                so = stage_objs.get(sn)
                if not so or so.status == 'PENDING':
                    current_stage = sn
                    break

        detailed_lead_times.append({
            'id': s.id,
            'site_id': s.site_id or '--',
            'name': s.name,
            'partner_company': partner or '--',
            'scope_type': s.get_scope_type_display(),
            'scope_key': scope,
            'created_at': creation_date,
            'transitions': site_transitions,
            'total_days': total_days,
            'total_display': f"{total_days} dias" if total_days is not None else f"Em andamento ({(today - creation_date).days}d)",
            'current_stage': current_stage,
            'is_finished': is_finished,
            'status': s.status,
            'get_status_display': s.get_status_display(),
        })

    # --- Agregar métricas por escopo ---
    scope_analytics = {}
    for scope, transitions in scope_stage_times.items():
        scope_display = dict(Site.ScopeType.choices).get(scope, scope)
        stages_list = []
        for label, times in transitions.items():
            avg = round(sum(times) / len(times), 1) if times else 0
            parts = label.split(" → ")
            prev_name = parts[0] if len(parts) > 0 else ""
            stage_name = parts[1] if len(parts) > 1 else ""
            stages_list.append({
                'label': label,
                'prev_name': prev_name,
                'stage_name': stage_name,
                'avg_days': avg,
                'min_days': min(times) if times else 0,
                'max_days': max(times) if times else 0,
                'count': len(times),
            })
        avg_total = round(sum(scope_totals[scope]) / len(scope_totals[scope]), 1) if scope_totals[scope] else None
        scope_analytics[scope] = {
            'display': scope_display,
            'stages': stages_list,
            'avg_total': avg_total,
            'total_sites': scope_counts.get(scope, {}).get('total', 0),
            'finished_sites': scope_counts.get(scope, {}).get('finished', 0),
        }

    # --- Agregar métricas por parceiro ---
    partner_stats = []
    for partner, data in partner_data.items():
        avg_total = round(sum(data['total_times']) / len(data['total_times']), 1) if data['total_times'] else None
        avg_survey = round(sum(data['survey_times']) / len(data['survey_times']), 1) if data['survey_times'] else None
        avg_report = round(sum(data['report_times']) / len(data['report_times']), 1) if data['report_times'] else None
        # Performance badge
        if avg_total is not None:
            if avg_total <= 8:
                perf_badge = 'fast'
            elif avg_total <= 15:
                perf_badge = 'normal'
            else:
                perf_badge = 'slow'
        else:
            perf_badge = 'none'

        partner_stats.append({
            'partner': partner,
            'total_sites': data['total_sites'],
            'finished_sites': data['finished_sites'],
            'avg_total_days': avg_total,
            'avg_survey_days': avg_survey,
            'avg_report_days': avg_report,
            'perf_badge': perf_badge,
            'scopes': data['scopes'],
        })

    # Ordena parceiros: mais rápido primeiro (sem dados por último)
    partner_stats.sort(key=lambda x: (x['avg_total_days'] is None, x['avg_total_days'] or 999))

    # KPIs globais
    all_total_times = []
    slowest_stage_name = None
    slowest_stage_avg = 0
    for scope, transitions in scope_stage_times.items():
        for label, times in transitions.items():
            avg = sum(times) / len(times) if times else 0
            if avg > slowest_stage_avg:
                slowest_stage_avg = avg
                slowest_stage_name = label
        all_total_times.extend(scope_totals.get(scope, []))

    overall_avg_total = round(sum(all_total_times) / len(all_total_times), 1) if all_total_times else None
    fastest_partner = partner_stats[0]['partner'] if partner_stats and partner_stats[0]['avg_total_days'] is not None else None
    total_finished = sum(sc.get('finished', 0) for sc in scope_counts.values())

    # Serializa dados para gráficos JS
    scope_chart_data = {}
    for scope, info in scope_analytics.items():
        scope_chart_data[scope] = {
            'labels': [s['label'] for s in info['stages']],
            'avg_days': [s['avg_days'] for s in info['stages']],
        }

    partner_chart_data = {
        'labels': [p['partner'] for p in partner_stats],
        'avg_total': [p['avg_total_days'] or 0 for p in partner_stats],
    }



    context = {
        'sites': sites,
        'sites_map': Site.objects.all(),
        'query': query,
        'total_sites': total_sites,
        'active_sites': active_sites,
        'maintenance_sites': maintenance_sites,
        'planned_sites': planned_sites,
        'inactive_sites': inactive_sites,
        'overdue_list': overdue_list,
        'alert_list': alert_list,
        'total_files': total_files,
        'pdf_files': pdf_files,
        'image_files': image_files,
        'dwg_files': dwg_files,
        'other_files': other_files,
        'recent_activities': recent_activities,
        # Analytics / Leadtime
        'scope_analytics': scope_analytics,
        'partner_stats': partner_stats,
        'detailed_lead_times': detailed_lead_times,
        'overall_avg_total': overall_avg_total,
        'slowest_stage_name': slowest_stage_name,
        'slowest_stage_avg': round(slowest_stage_avg, 1) if slowest_stage_avg else None,
        'fastest_partner': fastest_partner,
        'total_finished': total_finished,
        'scope_chart_data_json': _json.dumps(scope_chart_data),
        'partner_chart_data_json': _json.dumps(partner_chart_data),
    }

    return render(request, 'sites/site_list.html', context)


# --- DETALHES DO SITE E UPLOAD DE ARQUIVOS ---
@login_required
def site_detail(request, pk):
    site = get_object_or_404(Site, pk=pk)

    # Garante que o status do site seja recalculado e atualizado no carregamento
    old_status = site.status
    new_status = site.recalculate_status()
    if old_status != new_status:
        site.status = new_status
        site.save(update_fields=['status'])

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Ação 1: Atualização de cronogramas e fluxo de trabalho (apenas ADMIN ou ENGINEER)
        if action == 'update_workflow':
            if request.user.role not in [User.Role.ADMIN, User.Role.ENGINEER]:
                messages.error(request, "Seu cargo não possui permissão para atualizar prazos.")
                return redirect('site_detail', pk=pk)

            p_survey_str = request.POST.get('planned_survey_date')
            p_survey = parse_date(p_survey_str) if p_survey_str else None

            p_report_str = request.POST.get('planned_report_date')
            p_report = parse_date(p_report_str) if p_report_str else None

            a_survey_str = request.POST.get('actual_survey_date')
            a_survey = parse_date(a_survey_str) if a_survey_str else None

            a_report_str = request.POST.get('actual_report_date')
            a_report = parse_date(a_report_str) if a_report_str else None

            rescheduled_vistoria = False
            # Atualiza SiteStage de Vistoria
            vistoria_stage, _ = SiteStage.objects.get_or_create(
                site=site, stage_name='Vistoria',
                defaults={'scope_type': site.scope_type, 'order': 3}
            )
            # Detecta replanejamento de Vistoria
            if vistoria_stage.planned_date and p_survey and vistoria_stage.planned_date != p_survey:
                SiteStageReschedule.objects.create(
                    stage=vistoria_stage,
                    previous_date=vistoria_stage.planned_date,
                    new_date=p_survey,
                    reason=request.POST.get('reschedule_reason', '').strip() or None,
                    created_by=request.user,
                )
                rescheduled_vistoria = True
                site.reschedule_count = (site.reschedule_count or 0) + 1
                messages.warning(request, f"Replanejamento registrado! Total: {site.reschedule_count}")
            vistoria_stage.planned_date = p_survey
            vistoria_stage.actual_date  = a_survey
            vistoria_stage.status = 'DONE' if a_survey else 'PENDING'
            vistoria_stage.site = site
            vistoria_stage.save()

            # Atualiza SiteStage de Laudo ou Projeto
            report_name = 'Laudo' if site.scope_type == 'LAUDOS' else 'Projeto'
            laudo_stage, _ = SiteStage.objects.get_or_create(
                site=site, stage_name=report_name,
                defaults={'scope_type': site.scope_type, 'order': 4}
            )
            if laudo_stage.planned_date and p_report and laudo_stage.planned_date != p_report:
                SiteStageReschedule.objects.create(
                    stage=laudo_stage,
                    previous_date=laudo_stage.planned_date,
                    new_date=p_report,
                    reason=request.POST.get('reschedule_reason', '').strip() or None,
                    created_by=request.user,
                )
                if not rescheduled_vistoria:
                    site.reschedule_count = (site.reschedule_count or 0) + 1
                    messages.warning(request, f"Replanejamento registrado! Total: {site.reschedule_count}")
            laudo_stage.planned_date = p_report
            laudo_stage.actual_date  = a_report
            laudo_stage.status = 'DONE' if a_report else 'PENDING'
            laudo_stage.site = site
            laudo_stage.save()

            # Mantém campos legados sincronizados (compatibilidade com métricas de lead time)
            site.scope_type       = request.POST.get('scope_type') or site.scope_type
            site.partner_company  = request.POST.get('partner_company', '').strip() or None
            site.planned_survey_date = p_survey
            site.actual_survey_date  = a_survey
            site.planned_report_date = p_report
            site.actual_report_date  = a_report

            try:
                site.save()
                messages.success(request, "Fluxo de trabalho e prazos atualizados com sucesso!")
            except Exception as e:
                messages.error(request, f"Erro ao atualizar prazos: {str(e)}")

            return redirect('site_detail', pk=pk)

        # Ação Nova: Atualização do fluxo de acesso (apenas ADMIN ou ENGINEER)
        if action == 'update_access':
            if request.user.role not in [User.Role.ADMIN, User.Role.ENGINEER]:
                messages.error(request, "Seu cargo não possui permissão para atualizar controle de acesso.")
                return redirect('site_detail', pk=pk)

            access_action = request.POST.get('access_action')
            from django.utils import timezone
            today = timezone.localdate()

            if access_action == 'request_access':
                site.access_status = Site.AccessStatus.REQUESTED
                req_date_str = request.POST.get('access_requested_date')
                site.access_requested_date = parse_date(req_date_str) if req_date_str else today
                messages.success(request, "Acesso solicitado ao proprietário! Aguardando liberação.")
            elif access_action == 'release_access':
                site.access_status = Site.AccessStatus.RELEASED
                rel_date_str = request.POST.get('access_released_date')
                site.access_released_date = parse_date(rel_date_str) if rel_date_str else today
                messages.success(request, "Acesso liberado pelo proprietário! O parceiro já pode ser acionado.")
            elif access_action == 'skip_access':
                site.access_status = Site.AccessStatus.NOT_REQUIRED
                site.access_requested_date = None
                site.access_released_date = None
                messages.info(request, "Fluxo de liberação de acesso ignorado (Não necessário).")
            elif access_action == 'reset_access':
                site.access_status = Site.AccessStatus.NOT_STARTED
                site.access_requested_date = None
                site.access_released_date = None
                messages.info(request, "Controle de acesso reiniciado.")

            try:
                site.save()
            except Exception as e:
                messages.error(request, f"Erro ao salvar status de acesso: {str(e)}")
                
            return redirect('site_detail', pk=pk)

        # Ação Nova: Atualização de etapa dinâmica (apenas ADMIN ou ENGINEER)
        if action == 'update_stage':
            if request.user.role not in [User.Role.ADMIN, User.Role.ENGINEER]:
                messages.error(request, "Seu cargo não possui permissão para atualizar etapas.")
                return redirect('site_detail', pk=pk)

            stage_name   = request.POST.get('stage_name')
            stage_status = request.POST.get('stage_status')  # 'PENDING', 'DONE', 'SKIPPED'
            stage_date   = request.POST.get('stage_date')

            from django.utils import timezone
            today = timezone.localdate()

            stage_obj, _ = SiteStage.objects.get_or_create(
                site=site,
                stage_name=stage_name,
                defaults={'scope_type': site.scope_type, 'order': 99}
            )

            if stage_status == 'DONE':
                stage_obj.actual_date = parse_date(stage_date) if stage_date else today
                stage_obj.status = 'DONE'
            elif stage_status == 'SKIPPED':
                stage_obj.actual_date = None
                stage_obj.status = 'SKIPPED'
            else:
                stage_obj.actual_date = None
                stage_obj.status = 'PENDING'

            stage_obj.site = site
            stage_obj.save()

            if 'partner_company' in request.POST:
                site.partner_company = request.POST.get('partner_company', '').strip() or None

            try:
                site.save()
                messages.success(request, f"Etapa '{stage_name}' atualizada com sucesso!")
            except Exception as e:
                messages.error(request, f"Erro ao atualizar etapa: {str(e)}")

            return redirect('site_detail', pk=pk)

        # Ação Nova: Definir data planejada de etapa genérica
        if action == 'plan_stage':
            if request.user.role not in [User.Role.ADMIN, User.Role.ENGINEER]:
                messages.error(request, "Sem permissão para planejar etapas.")
                return redirect('site_detail', pk=pk)

            stage_name = request.POST.get('stage_name')
            planned_date_str = request.POST.get('stage_planned_date')

            stage_obj, _ = SiteStage.objects.get_or_create(
                site=site,
                stage_name=stage_name,
                defaults={'scope_type': site.scope_type, 'order': 99}
            )
            stage_obj.planned_date = parse_date(planned_date_str) if planned_date_str else None
            stage_obj.site = site
            stage_obj.save(update_fields=['planned_date', 'updated_at'])

            site.save()  # recalcula status
            messages.success(request, f"Data planejada para '{stage_name}' definida com sucesso!")
            return redirect('site_detail', pk=pk)

        # Ação Nova: Replanejar etapa genérica (nova data + motivo + histórico)
        if action == 'reschedule_stage':
            if request.user.role not in [User.Role.ADMIN, User.Role.ENGINEER]:
                messages.error(request, "Sem permissão para replanejar etapas.")
                return redirect('site_detail', pk=pk)

            stage_name = request.POST.get('stage_name')
            new_planned_date_str = request.POST.get('stage_planned_date')
            reason = request.POST.get('reschedule_reason', '').strip() or None

            stage_obj, _ = SiteStage.objects.get_or_create(
                site=site,
                stage_name=stage_name,
                defaults={'scope_type': site.scope_type, 'order': 99}
            )

            SiteStageReschedule.objects.create(
                stage=stage_obj,
                previous_date=stage_obj.planned_date,
                new_date=parse_date(new_planned_date_str) if new_planned_date_str else None,
                reason=reason,
                created_by=request.user,
            )

            stage_obj.planned_date = parse_date(new_planned_date_str) if new_planned_date_str else None
            stage_obj.site = site
            stage_obj.save(update_fields=['planned_date', 'updated_at'])

            site.reschedule_count = (site.reschedule_count or 0) + 1
            site.save()

            messages.warning(request, f"Replanejamento da etapa '{stage_name}' registrado! Total: {site.reschedule_count}")
            return redirect('site_detail', pk=pk)

        # Ação 3: Atualização de localização e ficha técnica (apenas ADMIN ou ENGINEER)
        if action == 'update_location':
            if request.user.role not in [User.Role.ADMIN, User.Role.ENGINEER]:
                messages.error(request, "Seu cargo não possui permissão para atualizar as informações do site.")
                return redirect('site_detail', pk=pk)

            # Editar ID do site (Código)
            if 'site_id' in request.POST:
                site_id_input = request.POST.get('site_id', '').strip() or None
                if site_id_input and site_id_input != site.site_id:
                    if Site.objects.exclude(pk=site.pk).filter(site_id=site_id_input).exists():
                        messages.error(request, f"Erro: Já existe um site cadastrado com o ID {site_id_input}.")
                        return redirect('site_detail', pk=pk)
                site.site_id = site_id_input

            # Editar Nome do site
            if 'name' in request.POST:
                name_input = request.POST.get('name', '').strip()
                if not name_input:
                    messages.error(request, "Erro: O nome do site não pode ser vazio.")
                    return redirect('site_detail', pk=pk)
                site.name = name_input

            # Editar Escopo do site
            if 'scope_type' in request.POST:
                scope_type_input = request.POST.get('scope_type')
                if scope_type_input in [Site.ScopeType.LAUDOS, Site.ScopeType.INSTALACAO, Site.ScopeType.INFRA, Site.ScopeType.FABRICA]:
                    site.scope_type = scope_type_input

            # Editar Parceiro / Fornecedora
            if 'partner_company' in request.POST:
                site.partner_company = request.POST.get('partner_company', '').strip() or None

            # Editar Situação do Acesso
            if 'access_status' in request.POST:
                access_status_input = request.POST.get('access_status')
                if access_status_input in [Site.AccessStatus.NOT_STARTED, Site.AccessStatus.REQUESTED, Site.AccessStatus.RELEASED, Site.AccessStatus.NOT_REQUIRED]:
                    site.access_status = access_status_input

            # Editar Operadora
            if 'operator' in request.POST:
                site.operator = request.POST.get('operator', '').strip() or None

            # Editar Tipo de estrutura e outros campos de geolocalização
            site.site_type = request.POST.get('site_type', site.site_type)
            site.address = request.POST.get('address', '').strip() or None
            
            if 'uf' in request.POST:
                site.uf = request.POST.get('uf', '').strip() or None
            
            lat_str = request.POST.get('latitude', '').strip()
            site.latitude = lat_str if lat_str else None
            
            lng_str = request.POST.get('longitude', '').strip()
            site.longitude = lng_str if lng_str else None

            # Editar Descrição / Observações
            if 'description' in request.POST:
                site.description = request.POST.get('description', '').strip() or None

            try:
                site.save()
                messages.success(request, "Informações do site e ficha técnica atualizadas com sucesso!")
            except Exception as e:
                messages.error(request, f"Erro ao atualizar informações do site: {str(e)}")
                
            return redirect('site_detail', pk=pk)

        # Ação 2: Upload de arquivos técnicos (Qualquer cargo)
        file_obj = request.FILES.get('file')
        category = request.POST.get('category')
        description = request.POST.get('description')

        if not file_obj:
            messages.error(request, "Nenhum arquivo enviado.")
            return redirect('site_detail', pk=pk)

        # Validação simples de tipo de arquivo com base na categoria
        ext = os.path.splitext(file_obj.name)[1].lower()
        if category == 'PDF' and ext != '.pdf':
            messages.error(request, "Erro: Categoria PDF exige arquivos com extensão .pdf")
            return redirect('site_detail', pk=pk)
        elif category == 'DWG' and ext != '.dwg':
            messages.error(request, "Erro: Categoria DWG exige arquivos com extensão .dwg")
            return redirect('site_detail', pk=pk)
        elif category == 'IMAGE' and ext not in ['.jpg', '.jpeg', '.png', '.gif']:
            messages.error(request, "Erro: Categoria Foto exige arquivos de imagem (.jpg, .png, etc.)")
            return redirect('site_detail', pk=pk)

        try:
            site_file = SiteFile.objects.create(
                site=site,
                file=file_obj,
                description=description,
                category=category,
                uploaded_by=request.user
            )
            messages.success(request, f"Arquivo '{os.path.basename(site_file.file.name)}' enviado com sucesso!")
        except Exception as e:
            messages.error(request, f"Erro no upload: {str(e)}")

        return redirect('site_detail', pk=pk)

    # Agrupa arquivos por categoria para organizar na tela
    files_by_category = {
        'PDF': site.files.filter(category='PDF'),
        'IMAGE': site.files.filter(category='IMAGE'),
        'DWG': site.files.filter(category='DWG'),
        'OTHER': site.files.filter(category='OTHER'),
    }

    # Gera a lista de etapas para o template a partir de SiteStage
    stages_list = []
    recommended_step = 1
    found_pending = False

    from django.utils import timezone as tz
    today = tz.localdate()

    stage_qs = site.stages.all().order_by('order')
    # Garante que os stages existam (para sites criados antes da migração)
    if not stage_qs.exists():
        site.ensure_stages_exist()
        stage_qs = site.stages.all().order_by('order')

    for idx, stage_obj in enumerate(stage_qs, 1):
        planned_date_obj = stage_obj.planned_date
        status = stage_obj.status
        date = stage_obj.actual_date
        reschedule_qs = stage_obj.reschedules.all()
        reschedule_count = reschedule_qs.count()
        history = [
            {
                'previous_date': r.previous_date,
                'new_date': r.new_date,
                'reason': r.reason,
                'by': (r.created_by.get_full_name() or r.created_by.username) if r.created_by else 'Sistema',
                'created_at': r.created_at.isoformat() if r.created_at else None,
            }
            for r in reschedule_qs
        ]

        is_due = bool(planned_date_obj and status == 'PENDING' and planned_date_obj <= today)
        is_overdue = bool(planned_date_obj and status == 'PENDING' and planned_date_obj < today)
        days_overdue = (today - planned_date_obj).days if is_overdue else 0

        stages_list.append({
            'name': stage_obj.stage_name,
            'status': status,
            'date': date.isoformat() if date else None,
            'index': idx,
            'planned_date': planned_date_obj,
            'is_due': is_due,
            'is_overdue': is_overdue,
            'days_overdue': days_overdue,
            'reschedule_count': reschedule_count,
            'reschedule_history': history,
        })

        if not found_pending and status == 'PENDING':
            recommended_step = idx
            found_pending = True

    if not found_pending and stages_list:
        recommended_step = len(stages_list)

    total_stages = len(stages_list)
    completed_stages = sum(1 for s in stages_list if s['status'] in ['DONE', 'SKIPPED'])
    progress_percent = int((completed_stages / total_stages) * 100) if total_stages > 0 else 0

    recommended_stage_name = "Concluído - Rollout Finalizado"
    for stage in stages_list:
        if stage['status'] == 'PENDING':
            recommended_stage_name = stage['name']
            break

    return render(request, 'sites/site_detail.html', {
        'site': site,
        'files_by_category': files_by_category,
        'categories': SiteFile.FileCategory.choices,
        'stages_list': stages_list,
        'recommended_step': recommended_step,
        'progress_percent': progress_percent,
        'recommended_stage_name': recommended_stage_name
    })


# --- DOWNLOAD SEGURO E DIRETO DO REPOSITÓRIO PERSISTIDO ---
@login_required
def download_file(request, file_id):
    site_file = get_object_or_404(SiteFile, id=file_id)

    # Regra de Controle de Acesso Baseada em Cargo (RBAC)
    # Exemplo: Técnicos de campo (TECHNICIAN) não podem baixar plantas em DWG (AutoCAD)
    if request.user.role == User.Role.TECHNICIAN and site_file.category == SiteFile.FileCategory.DWG:
        return HttpResponseForbidden("Acesso Negado: Técnicos de campo não possuem autorização para baixar plantas DWG.")

    file_path = site_file.file.path

    if not os.path.exists(file_path):
        raise Http404("O arquivo físico não foi encontrado no servidor.")

    # Adivinha o tipo MIME correto do arquivo
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'application/octet-stream'

    # Abre o arquivo em modo binário
    file_handle = open(file_path, 'rb')

    # Retorna o arquivo como resposta do tipo FileResponse
    response = FileResponse(file_handle, content_type=mime_type)
    
    # Extrai o nome de arquivo limpo (removendo caminhos de pastas)
    original_filename = os.path.basename(site_file.file.name)
    
    # Define o header: se for imagem ou PDF e não houver solicitação expressa de download, exibe inline
    force_download = request.GET.get('download') == 'true'
    if site_file.category in ['IMAGE', 'PDF'] and not force_download:
        response['Content-Disposition'] = f'inline; filename="{original_filename}"'
    else:
        response['Content-Disposition'] = f'attachment; filename="{original_filename}"'

    return response


# --- EXCLUSÃO SEGURA DE ARQUIVO TÉCNICO ---
@login_required
def delete_file(request, file_id):
    site_file = get_object_or_404(SiteFile, id=file_id)
    site_pk = site_file.site.pk
    
    try:
        # Tenta remover o arquivo físico do disco
        if site_file.file and os.path.exists(site_file.file.path):
            os.remove(site_file.file.path)
    except Exception:
        # Se o arquivo não existir fisicamente ou houver erro, apenas ignora para limpar o registro
        pass
        
    site_file.delete()
    messages.success(request, "Arquivo excluído com sucesso!")
    return redirect('site_detail', pk=site_pk)


# --- EXCLUSÃO SEGURA DE SITE / ATIVO (RBAC) ---
@login_required
def delete_site(request, pk):
    site = get_object_or_404(Site, pk=pk)

    # Restringe a permissão (apenas Admin ou Engenheiro)
    if request.user.role not in [User.Role.ADMIN, User.Role.ENGINEER]:
        messages.error(request, "Seu cargo não possui permissão para remover sites.")
        return redirect('site_detail', pk=pk)

    site_id = site.site_id

    # Exclui os arquivos físicos associados do disco
    import shutil
    from django.conf import settings
    
    for site_file in site.files.all():
        try:
            if site_file.file and os.path.exists(site_file.file.path):
                os.remove(site_file.file.path)
        except Exception:
            pass

    if site_id:
        site_dir = os.path.join(settings.MEDIA_ROOT, 'sites', site_id)
        if os.path.exists(site_dir):
            try:
                shutil.rmtree(site_dir)
            except Exception:
                pass

    # Exclui o site do banco de dados (cascade deleta os registros SiteFile)
    site.delete()
    messages.success(request, f"Site {site_id or site.name} removido com sucesso!")
    return redirect('site_list')


# --- APIS DO CALENDÁRIO ---

@login_required
def calendar_events_api(request):
    import datetime
    from django.http import JsonResponse
    from django.utils.dateparse import parse_date
    from .holidays import get_br_rj_holidays
    from .models import CalendarNote, Site
    from django.urls import reverse

    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    
    start_date = parse_date(start_str) if start_str else None
    end_date = parse_date(end_str) if end_str else None
    
    # Se nenhum intervalo for especificado, assume o ano atual
    if not start_date or not end_date:
        today = datetime.date.today()
        start_date = datetime.date(today.year, 1, 1)
        end_date = datetime.date(today.year, 12, 31)
        
    events = []
    
    # 1. Coleta Feriados
    years = range(start_date.year, end_date.year + 1)
    for year in years:
        year_holidays = get_br_rj_holidays(year)
        for h_date, h_name in year_holidays.items():
            if start_date <= h_date <= end_date:
                events.append({
                    'id': f"holiday_{h_date.isoformat()}_{h_name}",
                    'type': 'holiday',
                    'date': h_date.isoformat(),
                    'title': h_name,
                    'description': 'Feriado Nacional ou RJ'
                })
                
    # 2. Coleta Anotações/Notas do Usuário
    notes = CalendarNote.objects.filter(date__range=(start_date, end_date))
    for note in notes:
        events.append({
            'id': f"note_{note.id}",
            'type': 'note',
            'date': note.date.isoformat(),
            'title': note.title,
            'description': note.description or '',
            'note_id': note.id
        })
        
    # 3. Coleta Datas Planejadas de Sites no Data Room
    sites = Site.objects.all()
    for s in sites:
        # Vistoria Planejada
        if s.planned_survey_date and start_date <= s.planned_survey_date <= end_date:
            status = 'DONE' if s.actual_survey_date else 'PENDING'
            events.append({
                'id': f"site_survey_{s.id}",
                'type': 'planned_survey',
                'date': s.planned_survey_date.isoformat(),
                'title': f"Vistoria: {s.site_id or s.name}",
                'description': f"Vistoria planejada para o site {s.name}.",
                'site_id': s.id,
                'site_code': s.site_id or s.name,
                'status': status,
                'url': reverse('site_detail', kwargs={'pk': s.pk})
            })
            
        # Laudo/Projeto Planejado
        if s.planned_report_date and start_date <= s.planned_report_date <= end_date:
            status = 'DONE' if s.actual_report_date else 'PENDING'
            label = "Laudo" if s.scope_type == Site.ScopeType.LAUDOS else "Projeto"
            events.append({
                'id': f"site_report_{s.id}",
                'type': 'planned_report',
                'date': s.planned_report_date.isoformat(),
                'title': f"{label}: {s.site_id or s.name}",
                'description': f"{label} planejado para o site {s.name}.",
                'site_id': s.id,
                'site_code': s.site_id or s.name,
                'status': status,
                'url': reverse('site_detail', kwargs={'pk': s.pk})
            })
            
        # Outras etapas no JSON stages_status
        if s.stages_status:
            for stage_name, status_info in s.stages_status.items():
                if stage_name in ['Vistoria', 'Laudo', 'Projeto']:
                    continue
                planned_date_str = status_info.get('planned_date')
                if planned_date_str:
                    planned_date = parse_date(planned_date_str)
                    if planned_date and start_date <= planned_date <= end_date:
                        status = status_info.get('status', 'PENDING')
                        events.append({
                            'id': f"site_stage_{s.id}_{stage_name}",
                            'type': 'planned_stage',
                            'stage_name': stage_name,
                            'date': planned_date.isoformat(),
                            'title': f"{stage_name}: {s.site_id or s.name}",
                            'description': f"Etapa '{stage_name}' planejada para o site {s.name}.",
                            'site_id': s.id,
                            'site_code': s.site_id or s.name,
                            'status': status,
                            'url': reverse('site_detail', kwargs={'pk': s.pk})
                        })
                        
    return JsonResponse(events, safe=False)


from django.views.decorators.http import require_POST

@login_required
@require_POST
def add_calendar_note(request):
    from django.http import JsonResponse
    from django.utils.dateparse import parse_date
    from .models import CalendarNote
    
    date_str = request.POST.get('date')
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    
    date = parse_date(date_str) if date_str else None
    if not date or not title:
        return JsonResponse({'status': 'error', 'message': 'Data e Título são obrigatórios.'}, status=400)
        
    note = CalendarNote.objects.create(
        date=date,
        title=title,
        description=description
    )
    return JsonResponse({
        'status': 'success',
        'note': {
            'id': note.id,
            'date': note.date.isoformat(),
            'title': note.title,
            'description': note.description
        }
    })


@login_required
@require_POST
def edit_calendar_note(request):
    from django.http import JsonResponse
    from .models import CalendarNote
    
    note_id = request.POST.get('id')
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    
    if not note_id or not title:
        return JsonResponse({'status': 'error', 'message': 'ID e Título são obrigatórios.'}, status=400)
        
    try:
        note = CalendarNote.objects.get(id=note_id)
        note.title = title
        note.description = description
        note.save()
        return JsonResponse({
            'status': 'success',
            'note': {
                'id': note.id,
                'date': note.date.isoformat(),
                'title': note.title,
                'description': note.description
            }
        })
    except CalendarNote.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Nota não encontrada.'}, status=404)


@login_required
@require_POST
def delete_calendar_note(request):
    from django.http import JsonResponse
    from .models import CalendarNote
    
    note_id = request.POST.get('id')
    if not note_id:
        return JsonResponse({'status': 'error', 'message': 'ID é obrigatório.'}, status=400)
        
    try:
        note = CalendarNote.objects.get(id=note_id)
        note.delete()
        return JsonResponse({'status': 'success'})
    except CalendarNote.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Nota não encontrada.'}, status=404)



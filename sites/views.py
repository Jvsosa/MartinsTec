import os
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponseForbidden
from .models import Site, SiteFile, User
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
        latitude_str = request.POST.get('latitude', '').strip() or None
        longitude_str = request.POST.get('longitude', '').strip() or None
        scope_type = request.POST.get('scope_type')
        partner_company = request.POST.get('partner_company', '').strip() or None
        site_type = request.POST.get('site_type', Site.SiteType.ROOFTOP)
        
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
                latitude=latitude_str,
                longitude=longitude_str,
                scope_type=scope_type,
                partner_company=partner_company,
                site_type=site_type,
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

    # Filtragem de busca simples
    query = request.GET.get('q')
    if query:
        sites = Site.objects.filter(site_id__icontains=query) | Site.objects.filter(name__icontains=query)
    else:
        sites = Site.objects.all()

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

    # --- CÁLCULO DE MÉTRICAS E GARGALOS (LEAD TIMES E PERFORMANCE) ---
    partner_data = {}
    detailed_lead_times = []
    
    for s in Site.objects.all():
        partner = s.partner_company
        if not partner:
            continue
        partner = partner.strip()
        if partner not in partner_data:
            partner_data[partner] = {
                'total_sites': 0,
                'survey_times': [],
                'report_times': [],
                'total_times': [],
                'pending_surveys': 0,
                'pending_reports': 0,
            }
            
        p_data = partner_data[partner]
        p_data['total_sites'] += 1
        
        # 1. Acionamento -> Vistoria (Lead Time)
        creation_date = timezone.localdate(s.created_at)
        if s.actual_survey_date:
            survey_days = (s.actual_survey_date - creation_date).days
            p_data['survey_times'].append(max(0, survey_days))
            survey_display = f"{survey_days} dias"
        else:
            p_data['pending_surveys'] += 1
            elapsed_survey = (today - creation_date).days
            survey_display = f"Pendente ({elapsed_survey}d)"
            
        # 2. Vistoria -> Laudo (Lead Time)
        if s.actual_survey_date and s.actual_report_date:
            report_days = (s.actual_report_date - s.actual_survey_date).days
            p_data['report_times'].append(max(0, report_days))
            report_display = f"{report_days} dias"
        elif s.actual_survey_date and not s.actual_report_date:
            p_data['pending_reports'] += 1
            elapsed_report = (today - s.actual_survey_date).days
            report_display = f"Pendente ({elapsed_report}d)"
        else:
            report_display = "--"
            
        # 3. Ciclo Total (Acionamento -> Laudo)
        if s.actual_report_date:
            total_days = (s.actual_report_date - creation_date).days
            p_data['total_times'].append(max(0, total_days))
            total_display = f"{total_days} dias"
        else:
            elapsed_total = (today - creation_date).days
            total_display = f"Em andamento ({elapsed_total}d)"
            
        detailed_lead_times.append({
            'id': s.id,
            'site_id': s.site_id,
            'name': s.name,
            'partner_company': s.partner_company,
            'scope_type': s.get_scope_type_display(),
            'created_at': creation_date,
            'actual_survey_date': s.actual_survey_date,
            'actual_report_date': s.actual_report_date,
            'survey_display': survey_display,
            'report_display': report_display,
            'total_display': total_display,
            'status': s.status,
            'get_status_display': s.get_status_display(),
        })

    # Agregar médias por parceiro e totais gerais
    partner_stats = []
    all_survey_days = []
    all_report_days = []
    all_total_days = []
    
    for partner, data in partner_data.items():
        avg_survey = round(sum(data['survey_times']) / len(data['survey_times']), 1) if data['survey_times'] else None
        avg_report = round(sum(data['report_times']) / len(data['report_times']), 1) if data['report_times'] else None
        avg_total = round(sum(data['total_times']) / len(data['total_times']), 1) if data['total_times'] else None
        
        if avg_survey is not None:
            all_survey_days.append(avg_survey)
        if avg_report is not None:
            all_report_days.append(avg_report)
        if avg_total is not None:
            all_total_days.append(avg_total)
            
        partner_stats.append({
            'partner': partner,
            'total_sites': data['total_sites'],
            'avg_survey_days': avg_survey,
            'avg_report_days': avg_report,
            'avg_total_days': avg_total,
            'pending_surveys': data['pending_surveys'],
            'pending_reports': data['pending_reports'],
        })
        
    overall_avg_survey = round(sum(all_survey_days) / len(all_survey_days), 1) if all_survey_days else None
    overall_avg_report = round(sum(all_report_days) / len(all_report_days), 1) if all_report_days else None
    overall_avg_total = round(sum(all_total_days) / len(all_total_days), 1) if all_total_days else None

    context = {
        'sites': sites,
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
        'partner_stats': partner_stats,
        'detailed_lead_times': detailed_lead_times,
        'overall_avg_survey': overall_avg_survey,
        'overall_avg_report': overall_avg_report,
        'overall_avg_total': overall_avg_total,
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

            # Detectar replanejamento (mudança em datas planejadas que já existiam)
            is_reschedule = False
            if site.planned_survey_date and p_survey and site.planned_survey_date != p_survey:
                is_reschedule = True
            if site.planned_report_date and p_report and site.planned_report_date != p_report:
                is_reschedule = True
                
            if is_reschedule:
                site.reschedule_count += 1
                messages.warning(request, f"Replanejamento registrado! Total de replanejamentos deste site: {site.reschedule_count}")

            site.scope_type = request.POST.get('scope_type')
            site.partner_company = request.POST.get('partner_company', '').strip() or None
            site.planned_survey_date = p_survey
            site.planned_report_date = p_report
            
            a_survey = request.POST.get('actual_survey_date')
            site.actual_survey_date = parse_date(a_survey) if a_survey else None
            
            a_report = request.POST.get('actual_report_date')
            site.actual_report_date = parse_date(a_report) if a_report else None

            try:
                site.save()  # Auto-calcula o status
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
                site.access_requested_date = today
                messages.success(request, "Acesso solicitado ao proprietário! Aguardando liberação.")
            elif access_action == 'release_access':
                site.access_status = Site.AccessStatus.RELEASED
                site.access_released_date = today
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

            stage_name = request.POST.get('stage_name')
            stage_status = request.POST.get('stage_status')  # 'PENDING', 'DONE', 'SKIPPED'
            stage_date = request.POST.get('stage_date')

            if not site.stages_status:
                site.stages_status = {}

            from django.utils import timezone
            today = timezone.localdate()

            if stage_status == 'DONE':
                site.stages_status[stage_name] = {
                    'status': 'DONE',
                    'date': stage_date if stage_date else today.isoformat()
                }
            elif stage_status == 'SKIPPED':
                site.stages_status[stage_name] = {
                    'status': 'SKIPPED',
                    'date': today.isoformat()
                }
            else:
                site.stages_status[stage_name] = {
                    'status': 'PENDING',
                    'date': None
                }

            if 'partner_company' in request.POST:
                site.partner_company = request.POST.get('partner_company', '').strip() or None

            # Sincroniza o JSON de volta para os campos legados de banco
            site.sync_to_legacy_fields()

            try:
                site.save()
                messages.success(request, f"Etapa '{stage_name}' atualizada com sucesso!")
            except Exception as e:
                messages.error(request, f"Erro ao atualizar etapa: {str(e)}")

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

            # Editar Tipo de estrutura e outros campos de geolocalização
            site.site_type = request.POST.get('site_type', site.site_type)
            site.address = request.POST.get('address', '').strip() or None
            
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

    # Gera a lista de etapas para o template de forma estruturada
    stages_config = site.get_stages_config()
    stages_list = []
    recommended_step = 1
    found_pending = False
    
    for idx, name in enumerate(stages_config, 1):
        status_info = site.stages_status.get(name, {'status': 'PENDING', 'date': None})
        status = status_info.get('status', 'PENDING')
        date = status_info.get('date')
        
        stages_list.append({
            'name': name,
            'status': status,
            'date': date,
            'index': idx,
        })
        
        if not found_pending and status == 'PENDING':
            recommended_step = idx
            found_pending = True
            
    # Se todas as etapas foram concluídas ou puladas, foca na última
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

    site_dir = os.path.join(settings.MEDIA_ROOT, 'sites', site_id)
    if os.path.exists(site_dir):
        try:
            shutil.rmtree(site_dir)
        except Exception:
            pass

    # Exclui o site do banco de dados (cascade deleta os registros SiteFile)
    site.delete()
    messages.success(request, f"Site {site_id} removido com sucesso!")
    return redirect('site_list')


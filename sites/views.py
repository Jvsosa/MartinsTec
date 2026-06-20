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
        if site.actual_report_date:
            new_status = Site.SiteStatus.ACTIVE
        elif (site.planned_survey_date and site.planned_survey_date < today and not site.actual_survey_date) or \
             (site.planned_report_date and site.planned_report_date < today and not site.actual_report_date):
            new_status = Site.SiteStatus.INACTIVE
        elif (site.planned_survey_date and today <= site.planned_survey_date <= today + timezone.timedelta(days=3) and not site.actual_survey_date) or \
             (site.planned_report_date and today <= site.planned_report_date <= today + timezone.timedelta(days=3) and not site.actual_report_date):
            new_status = Site.SiteStatus.MAINTENANCE
        else:
            new_status = Site.SiteStatus.PLANNED
            
        if old_status != new_status:
            site.status = new_status
            site.save(update_fields=['status'])

    # Processa criação de novo site se for POST e o usuário tiver permissão (Admin ou Engenheiro)
    if request.method == 'POST':
        if request.user.role not in [User.Role.ADMIN, User.Role.ENGINEER]:
            messages.error(request, "Seu cargo não possui permissão para cadastrar sites.")
            return redirect('site_list')

        site_id = request.POST.get('site_id').strip().upper()
        name = request.POST.get('name').strip()
        latitude_str = request.POST.get('latitude')
        longitude_str = request.POST.get('longitude')
        scope_type = request.POST.get('scope_type')
        partner_company = request.POST.get('partner_company', '').strip() or None
        
        p_survey = request.POST.get('planned_survey_date')
        planned_survey_date = parse_date(p_survey) if p_survey else None
        
        p_report = request.POST.get('planned_report_date')
        planned_report_date = parse_date(p_report) if p_report else None
        
        description = request.POST.get('description')

        try:
            Site.objects.create(
                site_id=site_id,
                name=name,
                latitude=latitude_str,
                longitude=longitude_str,
                scope_type=scope_type,
                partner_company=partner_company,
                planned_survey_date=planned_survey_date,
                planned_report_date=planned_report_date,
                description=description
            )
            messages.success(request, f"Site {site_id} cadastrado com sucesso!")
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
    }

    return render(request, 'sites/site_list.html', context)


# --- DETALHES DO SITE E UPLOAD DE ARQUIVOS ---
@login_required
def site_detail(request, pk):
    site = get_object_or_404(Site, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Ação 1: Atualização de cronogramas e fluxo de trabalho (apenas ADMIN ou ENGINEER)
        if action == 'update_workflow':
            if request.user.role not in [User.Role.ADMIN, User.Role.ENGINEER]:
                messages.error(request, "Seu cargo não possui permissão para atualizar prazos.")
                return redirect('site_detail', pk=pk)

            site.scope_type = request.POST.get('scope_type')
            site.partner_company = request.POST.get('partner_company', '').strip() or None
            
            p_survey = request.POST.get('planned_survey_date')
            site.planned_survey_date = parse_date(p_survey) if p_survey else None
            
            a_survey = request.POST.get('actual_survey_date')
            site.actual_survey_date = parse_date(a_survey) if a_survey else None
            
            p_report = request.POST.get('planned_report_date')
            site.planned_report_date = parse_date(p_report) if p_report else None
            
            a_report = request.POST.get('actual_report_date')
            site.actual_report_date = parse_date(a_report) if a_report else None

            try:
                site.save()  # Auto-calcula o status
                messages.success(request, "Fluxo de trabalho e prazos atualizados com sucesso!")
            except Exception as e:
                messages.error(request, f"Erro ao atualizar prazos: {str(e)}")
                
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

    return render(request, 'sites/site_detail.html', {
        'site': site,
        'files_by_category': files_by_category,
        'categories': SiteFile.FileCategory.choices
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

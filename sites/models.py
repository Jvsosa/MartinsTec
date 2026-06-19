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
        PLANNED = 'PLANNED', 'Planejado'
        ACTIVE = 'ACTIVE', 'Ativo'
        MAINTENANCE = 'MAINTENANCE', 'Em Manutenção'
        INACTIVE = 'INACTIVE', 'Inativo'

    site_id = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="ID do Site (Código)"
    )
    name = models.CharField(max_length=100, verbose_name="Nome do Site")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Latitude")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Longitude")
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

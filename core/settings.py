import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env local
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Detecta se está rodando no ambiente de produção do Render
IS_RENDER = os.environ.get('RENDER') == 'true'

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-local-dev-key-telecom-eng-983172')

DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

if IS_RENDER:
    # URL externa fornecida pelo Render
    ALLOWED_HOSTS = [os.environ.get('RENDER_EXTERNAL_HOSTNAME', '*')]
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Configuração do Modelo de Usuário Customizado (RBAC)
AUTH_USER_MODEL = 'sites.User'

# Aplicativos Instalados
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Aplicativos locais
    'sites.apps.SitesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Para arquivos estáticos eficientes
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Configuração do Banco de Dados
if IS_RENDER:
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Validação de Senhas
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Configurações de Internacionalização
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Arquivos Estáticos (CSS, JS, Imagens do Painel)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise para comprimir e cachear estáticos
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Configurações do Render Persistent Disk para Mídias (Arquivos de Sites)
if IS_RENDER:
    # No Render, o disco persistente é montado em um caminho absoluto
    MEDIA_ROOT = '/var/lib/data/media'
else:
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

MEDIA_URL = '/media/'

# Garante que o diretório de mídias exista
os.makedirs(MEDIA_ROOT, exist_ok=True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configurações de Autenticação/Redirecionamento
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'site_list'
LOGOUT_REDIRECT_URL = 'login'

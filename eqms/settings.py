"""
Django settings for EQMS-AlgoriSync project.

Deployment-overridable via environment variables:

  EQMS_SECRET_KEY          Django secret key (any string; use something long)
  EQMS_DEBUG               'True' / 'False' (default True)
  EQMS_ALLOWED_HOSTS       comma-separated hosts/IPs (default '*')
  EQMS_CSRF_TRUSTED_ORIGINS  comma-separated, e.g. http://192.168.1.10:8000
  EQMS_DB_PATH             SQLite file path (default <project>/db.sqlite3)
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(name, default=None):
    val = os.environ.get(name)
    if not val:
        return list(default or [])
    return [item.strip() for item in val.split(',') if item.strip()]


SECRET_KEY = os.environ.get(
    'EQMS_SECRET_KEY',
    'django-insecure-lwz$@%6cf^ssm12tg7b+7+p8g-bef%8r!974pr8ub5z^4!k-9)',
)

DEBUG = _env_bool('EQMS_DEBUG', True)

# Default '*' makes it easy to reach the server from any IP on the network
ALLOWED_HOSTS = _env_list('EQMS_ALLOWED_HOSTS', ['*']) or ['*']

CSRF_TRUSTED_ORIGINS = _env_list('EQMS_CSRF_TRUSTED_ORIGINS', [])

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'channels',
    'django_cleanup.apps.CleanupConfig',
    'core',
    'accounts',
    'kiosk',
    'counter',
    'display',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'eqms.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'eqms.wsgi.application'
ASGI_APPLICATION = 'eqms.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('EQMS_DB_PATH', str(BASE_DIR / 'db.sqlite3')),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Audio settings
AUDIO_DIR = BASE_DIR / 'static' / 'audio'

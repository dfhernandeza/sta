from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# Usar almacenamiento estático simple en tests/desarrollo (sin manifest)
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# SQLite para desarrollo local (sin necesidad de PostgreSQL instalado)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Para usar PostgreSQL en desarrollo, comenta el bloque anterior y descomenta este:
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': config('DB_NAME', default='sta_db'),
#         'USER': config('DB_USER', default='postgres'),
#         'PASSWORD': config('DB_PASSWORD', default=''),
#         'HOST': config('DB_HOST', default='localhost'),
#         'PORT': config('DB_PORT', default='5432'),
#     }
# }


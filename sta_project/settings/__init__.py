from decouple import config


# Select settings module dynamically from .env (DJANGO_ENV=development|production).
DJANGO_ENV = config('DJANGO_ENV', default='development').strip().lower()

if DJANGO_ENV == 'production':
	from .production import *  # noqa: F403,F401
else:
	from .development import *  # noqa: F403,F401

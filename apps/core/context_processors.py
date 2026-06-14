from pathlib import Path
from django.conf import settings


def logo_exists(request):
    logo_path = Path(settings.BASE_DIR) / 'static' / 'img' / 'logo.png'
    return {'logo_exists': logo_path.exists()}

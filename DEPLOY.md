# ================================================================
# STA - Guía de Despliegue en VPS (Ubuntu 22.04)
# ================================================================

## 1. Preparar el servidor

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib nginx certbot python3-certbot-nginx
```

## 2. Crear base de datos PostgreSQL

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE sta_db;
CREATE USER sta_user WITH PASSWORD 'TuPasswordSegura123!';
ALTER ROLE sta_user SET client_encoding TO 'utf8';
ALTER ROLE sta_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE sta_user SET timezone TO 'America/Santiago';
GRANT ALL PRIVILEGES ON DATABASE sta_db TO sta_user;
\q
```

## 3. Subir el proyecto al servidor

```bash
# En tu máquina local (desde la raíz del proyecto):
rsync -avz --exclude='venv/' --exclude='__pycache__/' --exclude='*.pyc' \
      --exclude='.env' --exclude='db.sqlite3' \
      ./ usuario@TU_IP:/var/www/sta/
```

## 4. Configurar entorno en el servidor

```bash
cd /var/www/sta

# Crear virtualenv
python3.11 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# Crear archivo .env de producción
nano .env
```

Contenido del `.env` de producción:

```
SECRET_KEY=genera-una-clave-segura-con-50-caracteres-aleatorios
DEBUG=False
ALLOWED_HOSTS=tudominio.cl,www.tudominio.cl,TU_IP_VPS
DB_NAME=sta_db
DB_USER=sta_user
DB_PASSWORD=TuPasswordSegura123!
DB_HOST=localhost
DB_PORT=5432
```

Generar SECRET_KEY:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 5. Apuntar manage.py a settings de producción

Editar `manage.py` línea `DJANGO_SETTINGS_MODULE`:
```python
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sta_project.settings.production')
```

También editar `sta_project/wsgi.py` de la misma forma.

## 6. Preparar el proyecto

```bash
cd /var/www/sta
source venv/bin/activate

# Migraciones
python manage.py migrate

# Archivos estáticos
python manage.py collectstatic --no-input

# Crear superusuario
python manage.py createsuperuser
# → Ingresa usuario, email y contraseña cuando se solicite

# Crear directorios de logs
sudo mkdir -p /var/log/sta
sudo chown www-data:www-data /var/log/sta
```

## 7. Configurar Gunicorn como servicio systemd

```bash
sudo cp /var/www/sta/sta.service /etc/systemd/system/sta.service
sudo systemctl daemon-reload
sudo systemctl enable sta
sudo systemctl start sta
sudo systemctl status sta
```

## 8. Configurar Nginx

```bash
sudo cp /var/www/sta/nginx.conf.example /etc/nginx/sites-available/sta
# Editar el archivo y reemplazar tudominio.cl con tu dominio real
sudo nano /etc/nginx/sites-available/sta

sudo ln -s /etc/nginx/sites-available/sta /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 9. Configurar SSL con Let's Encrypt

```bash
sudo certbot --nginx -d tudominio.cl -d www.tudominio.cl
```

## 10. Permisos del directorio de medios

```bash
sudo chown -R www-data:www-data /var/www/sta/media/
sudo chmod -R 755 /var/www/sta/media/
```

## 11. Verificar

- Sitio web: https://tudominio.cl/
- Panel admin: https://tudominio.cl/gestion/login/
- Django admin nativo: https://tudominio.cl/django-admin/

## Comandos útiles post-deploy

```bash
# Reiniciar app tras cambios de código
sudo systemctl restart sta

# Ver logs en tiempo real
sudo journalctl -u sta -f
sudo tail -f /var/log/sta/gunicorn_error.log

# Ejecutar comandos Django en producción
cd /var/www/sta && source venv/bin/activate
python manage.py shell

# Backup de base de datos
pg_dump -U sta_user sta_db > backup_$(date +%Y%m%d).sql
```

## Logo

Copia tu logo PNG a `static/img/logo.png` antes de hacer `collectstatic`.
El template `base_web.html` lo referencia como `{% static 'img/logo.png' %}`.

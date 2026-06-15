# STA - Runbook Ejecutable de Produccion (Ubuntu + Nginx + Gunicorn + PostgreSQL + GitHub Actions)

Este documento es una guia de ejecucion paso a paso para levantar STA desde una VM Ubuntu limpia.

## 0) Variables de referencia (reemplazar antes de ejecutar)

- Dominio: `stasoluciones.cl`
- Dominio alterno: `www.stasoluciones.cl`
- IP publica VM: `170.239.85.202`
- Usuario admin inicial VM: `ubuntu`
- Usuario deploy: `deploy`
- Ruta app: `/var/www/sta`
- Servicio systemd app: `sta`
- Repo SSH: `git@github.com:dfhernandeza/sta.git`

---

## 1) Preparacion local (ya en tu equipo)

```bash
# Inicializa el repositorio Git en la carpeta actual.
git init
# Renombra o crea la rama principal con nombre main.
git branch -M main
# Agrega todos los archivos al area de preparacion (staging).
git add .
# Crea el primer commit con el mensaje indicado.
git commit -m "initial: sta"
# Configura el remoto origin apuntando a GitHub por SSH.
git remote add origin git@github.com:dfhernandeza/sta.git
# Sube la rama main al remoto y deja tracking configurado.
git push -u origin main
```

---

## 2) Bootstrap de VM Ubuntu limpia

Conectate por SSH y ejecuta:

```bash
# Actualiza el indice de paquetes y aplica actualizaciones del sistema.
sudo apt update && sudo apt upgrade -y
# Ajusta la zona horaria del servidor.
sudo timedatectl set-timezone America/Santiago
# Instala dependencias base: Python, PostgreSQL, Nginx, firewall, Certbot, Git y fail2ban.
sudo apt install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib nginx ufw certbot python3-certbot-nginx git fail2ban
```

Crear usuario y estructura:

```bash
# Crea el usuario deploy sin contraseña interactiva.
sudo adduser --disabled-password --gecos "" deploy
# Agrega deploy al grupo www-data para compartir permisos con servicios web.
sudo usermod -aG www-data deploy

# Crea carpetas de aplicacion, logs, runtime y respaldos.
sudo mkdir -p /var/www/sta /var/log/sta /var/run/sta /var/backups/sta
# Asigna propiedad del codigo a deploy y grupo web.
sudo chown -R deploy:www-data /var/www/sta
# Asigna propiedad de logs y runtime a www-data.
sudo chown -R www-data:www-data /var/log/sta /var/run/sta
# Da permisos de lectura/escritura al owner y grupo en logs/runtime.
sudo chmod 775 /var/log/sta /var/run/sta
```

Firewall:

```bash
# Permite trafico SSH en el firewall.
sudo ufw allow OpenSSH
# Permite trafico HTTP.
sudo ufw allow 80/tcp
# Permite trafico HTTPS.
sudo ufw allow 443/tcp
# Activa UFW sin pedir confirmacion interactiva.
sudo ufw --force enable
# Muestra el estado y reglas activas del firewall.
sudo ufw status
```

Hardening SSH basico:

```bash
# Respaldar configuracion SSH actual antes de editar.
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
# Deshabilita autenticacion por contraseña (solo llaves).
sudo sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
# Impide login SSH del usuario root.
sudo sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
# Reinicia el servicio SSH para aplicar cambios.
sudo systemctl restart ssh
```

---

## 3) PostgreSQL (base y usuario dedicados)

```bash
# Entra al cliente psql como usuario postgres del sistema.
sudo -u postgres psql
```

```sql
-- Crea la base de datos de la aplicacion.
CREATE DATABASE sta_db;
-- Crea el usuario de BD que usara Django.
CREATE USER sta_user WITH PASSWORD 'CAMBIA_ESTA_PASSWORD';
-- Define codificacion UTF-8 por defecto para el rol.
ALTER ROLE sta_user SET client_encoding TO 'utf8';
-- Define aislamiento de transacciones recomendado.
ALTER ROLE sta_user SET default_transaction_isolation TO 'read committed';
-- Define zona horaria de sesion para el rol.
ALTER ROLE sta_user SET timezone TO 'America/Santiago';
-- Otorga privilegios sobre la base al usuario de aplicacion.
GRANT ALL PRIVILEGES ON DATABASE sta_db TO sta_user;
-- Sale del cliente psql.
\q
```

---

## 4) Clonar app y preparar Python

```bash
# Clona el repositorio en la ruta final ejecutando como deploy.
sudo -u deploy -H bash -lc "cd /var/www/sta && git clone git@github.com:dfhernandeza/sta.git ."
# Crea un entorno virtual Python aislado para la app.
sudo -u deploy -H bash -lc "cd /var/www/sta && python3.11 -m venv venv"
# Activa venv e instala/actualiza dependencias del proyecto.
sudo -u deploy -H bash -lc "cd /var/www/sta && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
```

Generar SECRET_KEY:

```bash
# Genera una SECRET_KEY segura desde Django para produccion.
sudo -u deploy -H bash -lc "cd /var/www/sta && source venv/bin/activate && python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
```

Crear `.env` de produccion:

```bash
# Abre el archivo .env para configurar variables sensibles de produccion.
sudo -u deploy -H nano /var/www/sta/.env
```

Contenido:

```env
DJANGO_ENV=production
SECRET_KEY=PEGA_SECRET_KEY_GENERADA
DEBUG=False
ALLOWED_HOSTS=stasoluciones.cl,www.stasoluciones.cl,170.239.85.202
DB_NAME=sta_db
DB_USER=sta_user
DB_PASSWORD=CAMBIA_ESTA_PASSWORD
DB_HOST=localhost
DB_PORT=5432
```

Permisos `.env`:

```bash
# Ajusta propietario del .env para acceso controlado.
sudo chown deploy:www-data /var/www/sta/.env
# Permite lectura al grupo y bloquea acceso a otros usuarios.
sudo chmod 640 /var/www/sta/.env
```

---

## 5) Ajustes obligatorios de settings para produccion

Asegura estos valores en el codigo:

- `manage.py` -> `sta_project.settings`
- `sta_project/wsgi.py` -> `sta_project.settings`
- `sta_project/asgi.py` -> `sta_project.settings`
- `sta_project/settings/__init__.py` -> seleccionar automaticamente segun `DJANGO_ENV`

> Con esta configuracion, el entorno se decide automaticamente desde `.env` usando `DJANGO_ENV=development` o `DJANGO_ENV=production`.

---

## 6) Migraciones, estaticos y superusuario

```bash
# Valida configuracion de seguridad recomendada para despliegue.
sudo -u deploy -H bash -lc "cd /var/www/sta && source venv/bin/activate && python manage.py check --deploy"
# Aplica migraciones pendientes en PostgreSQL.
sudo -u deploy -H bash -lc "cd /var/www/sta && source venv/bin/activate && python manage.py migrate --noinput"
# Recolecta estaticos en STATIC_ROOT para servir por Nginx/WhiteNoise.
sudo -u deploy -H bash -lc "cd /var/www/sta && source venv/bin/activate && python manage.py collectstatic --noinput"
# Crea el usuario administrador inicial de Django.
sudo -u deploy -H bash -lc "cd /var/www/sta && source venv/bin/activate && python manage.py createsuperuser"
```

Permisos runtime:

```bash
# Da propiedad de media y staticfiles al usuario/grupo del servicio web.
sudo chown -R www-data:www-data /var/www/sta/media /var/www/sta/staticfiles
# Permite lectura/ejecucion para servir archivos desde Nginx.
sudo chmod -R 755 /var/www/sta/media /var/www/sta/staticfiles
```

---

## 7) Systemd para Gunicorn

```bash
# Copia la unidad systemd de la app a la ruta de servicios del sistema.
sudo cp /var/www/sta/sta.service /etc/systemd/system/sta.service
# Recarga definiciones de systemd tras agregar/modificar unidades.
sudo systemctl daemon-reload
# Habilita inicio automatico del servicio en cada boot.
sudo systemctl enable sta
# Inicia el servicio inmediatamente.
sudo systemctl start sta
# Muestra estado actual del servicio sin paginador.
sudo systemctl status sta --no-pager
# Muestra las ultimas lineas de logs del servicio.
sudo journalctl -u sta -n 100 --no-pager
```

---

## 8) Nginx + HTTPS

```bash
# Copia la configuracion del sitio Nginx a sites-available.
sudo cp /var/www/sta/nginx.conf.example /etc/nginx/sites-available/sta
# Edita server_name, rutas y parametros necesarios del sitio.
sudo nano /etc/nginx/sites-available/sta
# Habilita el sitio creando enlace simbolico en sites-enabled.
sudo ln -s /etc/nginx/sites-available/sta /etc/nginx/sites-enabled/sta
# Valida sintaxis de configuracion Nginx.
sudo nginx -t
# Recarga Nginx sin cortar conexiones activas.
sudo systemctl reload nginx
# Solicita e instala certificado TLS de Let's Encrypt.
sudo certbot --nginx -d stasoluciones.cl -d www.stasoluciones.cl
# Recarga Nginx despues de configurar certificados.
sudo systemctl reload nginx
```

---

## 9) Validacion de salida

```bash
# Consulta encabezados HTTP del dominio principal (salud y TLS).
curl -I https://stasoluciones.cl
# Consulta encabezados de la ruta de login del panel.
curl -I https://stasoluciones.cl/gestion/login/
# Verifica que PostgreSQL este activo.
sudo systemctl is-active postgresql
# Verifica que Nginx este activo.
sudo systemctl is-active nginx
# Verifica que el servicio de la app este activo.
sudo systemctl is-active sta
```

---

## 10) Backups automaticos PostgreSQL

Crear script:

```bash
# Crea/edita el script de respaldo diario de PostgreSQL.
sudo nano /usr/local/bin/sta_backup.sh
```

Contenido:

```bash
#!/usr/bin/env bash
# Hace que el script falle ante errores, variables no definidas o fallos en pipes.
set -euo pipefail
# Genera marca de tiempo para nombrar el respaldo.
TS=$(date +%F_%H-%M-%S)
# Define ruta de salida del archivo comprimido.
OUT=/var/backups/sta/sta_db_${TS}.sql.gz
# Exporta la base y comprime el dump en una sola linea.
PGPASSWORD='CAMBIA_ESTA_PASSWORD' pg_dump -h localhost -U sta_user sta_db | gzip > ${OUT}
# Elimina respaldos con mas de 14 dias de antiguedad.
find /var/backups/sta -type f -name 'sta_db_*.sql.gz' -mtime +14 -delete
```

Permisos y cron:

```bash
# Da permisos de ejecucion al owner y grupo del script.
sudo chmod 750 /usr/local/bin/sta_backup.sh
# Define propietario root y grupo web para control de acceso.
sudo chown root:www-data /usr/local/bin/sta_backup.sh
# Abre el crontab de root para programar ejecucion automatica.
sudo crontab -e
```

Cron diario (02:30):

```cron
# Ejecuta backup cada dia a las 02:30 y guarda log de ejecucion.
30 2 * * * /usr/local/bin/sta_backup.sh >> /var/log/sta/backup.log 2>&1
```

---

## 11) GitHub Actions (CI/CD)

### 11.1 Secrets en GitHub

Configura en `Settings -> Secrets and variables -> Actions`:

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`

### 11.2 Sudo minimo para deploy

```bash
# Abre sudoers dedicado para permisos minimos de deploy.
sudo visudo -f /etc/sudoers.d/deploy-sta
```

Contenido:

```sudoers
deploy ALL=(ALL) NOPASSWD:/bin/systemctl restart sta,/bin/systemctl status sta
```

### 11.3 Crear workflow

Crea el archivo `.github/workflows/ci-cd.yml` con:

```yaml
name: CI-CD

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: sta_test
          POSTGRES_USER: sta_user
          POSTGRES_PASSWORD: test_pass
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U sta_user -d sta_test"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 10
    env:
      DJANGO_SETTINGS_MODULE: sta_project.settings
      DJANGO_ENV: production
      SECRET_KEY: ci-secret-key
      ALLOWED_HOSTS: localhost,127.0.0.1
      DB_NAME: sta_test
      DB_USER: sta_user
      DB_PASSWORD: test_pass
      DB_HOST: 127.0.0.1
      DB_PORT: 5432
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      # Instala dependencias Python del proyecto.
      - run: pip install -r requirements.txt
      # Ejecuta chequeos de despliegue seguro en Django.
      - run: python manage.py check --deploy
      # Verifica que no falten migraciones por generar.
      - run: python manage.py makemigrations --dry-run --check
      # Aplica migraciones en la base temporal de CI.
      - run: python manage.py migrate --noinput
      # Simula collectstatic para validar estaticos sin escribir.
      - run: python manage.py collectstatic --noinput --dry-run
      # Ejecuta pruebas automaticas del proyecto.
      - run: python manage.py test

  cd:
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    needs: ci
    runs-on: ubuntu-latest
    steps:
      - name: Setup SSH key
        run: |
          # Crea carpeta SSH del runner.
          mkdir -p ~/.ssh
          # Escribe la clave privada desde GitHub Secrets.
          echo "${{ secrets.DEPLOY_SSH_KEY }}" > ~/.ssh/id_ed25519
          # Restringe permisos de la clave para que SSH la acepte.
          chmod 600 ~/.ssh/id_ed25519
          # Agrega huella del servidor para evitar prompt interactivo.
          ssh-keyscan -p "${{ secrets.DEPLOY_PORT }}" "${{ secrets.DEPLOY_HOST }}" >> ~/.ssh/known_hosts

      - name: Deploy on server
        run: |
          ssh -p "${{ secrets.DEPLOY_PORT }}" "${{ secrets.DEPLOY_USER }}@${{ secrets.DEPLOY_HOST }}" '
            # Falla de inmediato si algun comando da error.
            set -e
            # Entra a la carpeta del proyecto en servidor.
            cd /var/www/sta
            # Actualiza referencias remotas del repositorio.
            git fetch --all
            # Sincroniza exacto con la rama main remota.
            git reset --hard origin/main
            # Activa entorno virtual Python del servidor.
            source venv/bin/activate
            # Instala/actualiza dependencias del despliegue.
            pip install -r requirements.txt
            # Ejecuta migraciones pendientes en produccion.
            python manage.py migrate --noinput
            # Actualiza archivos estaticos para Nginx/WhiteNoise.
            python manage.py collectstatic --noinput
            # Reinicia servicio app para aplicar nueva version.
            sudo systemctl restart sta
            # Muestra estado final del servicio tras despliegue.
            sudo systemctl status sta --no-pager
          '
```

---

## 12) Rollback rapido

```bash
# Entra al directorio de la aplicacion para operar rollback.
cd /var/www/sta
# Muestra ultimos commits para elegir destino de rollback.
git log --oneline -n 5
# Revierte el arbol de trabajo al commit indicado.
git reset --hard COMMIT_ANTERIOR
# Activa entorno virtual antes de comandos Django.
source venv/bin/activate
# Aplica migraciones coherentes con la version restaurada.
python manage.py migrate --noinput
# Regenera estaticos de la version restaurada.
python manage.py collectstatic --noinput
# Reinicia servicio para dejar rollback activo.
sudo systemctl restart sta
```

---

## 13) Checklist final

- [ ] `python manage.py check --deploy` sin errores criticos
- [ ] `sta`, `nginx`, `postgresql` activos
- [ ] login en `/gestion/login/` operativo por HTTPS
- [ ] archivos estaticos y media cargan bien
- [ ] backup diario creado
- [ ] workflow CI/CD ejecuta en push a `main`

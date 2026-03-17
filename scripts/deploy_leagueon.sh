#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/leagueon/app"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="leagueon.service"

cd "$APP_DIR"

git fetch origin main
git reset --hard origin/main

source "$VENV_DIR/bin/activate"

pip install -r requirements.txt

python -m py_compile app.py admin.py auth.py models.py league.py
python -c "from jinja2 import Environment, FileSystemLoader; env=Environment(loader=FileSystemLoader('templates')); [env.get_template(name) for name in ['index.html','admin.html','login.html','_theme_head.html','_csrf_token.html','admin_overview.html']]; print('templates ok')"

sudo systemctl restart "$SERVICE_NAME"
sudo systemctl --no-pager --full status "$SERVICE_NAME"

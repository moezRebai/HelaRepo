#!/usr/bin/env bash
# Provisionne un serveur web — script Bitbucket "legacy" à convertir.
set -euo pipefail

APP_PORT="${APP_PORT:-8080}"
APP_USER="appsvc"

echo "[1/5] Installation nginx"
apt-get update -y
apt-get install -y nginx

echo "[2/5] Création utilisateur ${APP_USER}"
if ! id "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --no-create-home "${APP_USER}"
fi

echo "[3/5] Déploiement config"
mkdir -p /etc/myapp
cat > /etc/myapp/app.conf <<EOF
listen_port=${APP_PORT}
run_as=${APP_USER}
EOF

echo "[4/5] Activation service"
systemctl enable nginx
systemctl restart nginx

echo "[5/5] Health check"
python3 "$(dirname "$0")/health_check.py" "${APP_PORT}"

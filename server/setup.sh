#!/usr/bin/env bash
# Первичная настройка чистого сервера Ubuntu 24.04 (Selectel) и запуск HR-метрик.
# Запуск от root из папки проекта:  bash server/setup.sh
# Повторный запуск безопасен: обновит систему, пересоберёт и перезапустит приложение.
set -euo pipefail
cd "$(dirname "$0")"
[ "$(id -u)" = 0 ] || { echo "Запустите от root: sudo bash server/setup.sh"; exit 1; }

echo "== Обновления системы и защита"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q && apt-get upgrade -yq
apt-get install -yq ca-certificates openssl ufw fail2ban unattended-upgrades docker.io docker-compose-v2
dpkg-reconfigure -f noninteractive unattended-upgrades          # автоматические обновления безопасности
systemctl enable --now fail2ban docker

echo "== Файрвол: открыты только SSH, 80 и 443"
ufw default deny incoming; ufw default allow outgoing
ufw allow OpenSSH; ufw allow 80/tcp; ufw allow 443/tcp
ufw --force enable

echo "== SSH: вход только по ключу"
if [ -s /root/.ssh/authorized_keys ]; then
  printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin prohibit-password\n' > /etc/ssh/sshd_config.d/90-hr.conf
  systemctl reload ssh
else
  echo "  ВНИМАНИЕ: SSH-ключ не добавлен — вход по паролю оставлен. Добавьте ключ и запустите скрипт снова."
fi

echo "== Настройки приложения"
if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s|^SESSION_SECRET=.*|SESSION_SECRET=$(openssl rand -base64 48 | tr -d '\n')|" .env
fi
chmod 600 .env
if grep -qE '^(OAUTH_CLIENT_ID|OAUTH_CLIENT_SECRET)=$|example\.ru' .env; then
  echo "  Заполните server/.env (домен, почты, ключи приложения Яндекс ID) и запустите скрипт ещё раз."
  exit 0
fi

echo "== Запуск"
mkdir -p data && chown 1000:1000 data && chmod 700 data
docker compose up -d --build
sleep 3; docker compose ps
. ./.env
echo "Готово: $BASE_URL — войдите почтой $ADMIN_EMAILS."

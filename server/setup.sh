#!/usr/bin/env bash
# Первичная настройка чистого сервера Ubuntu 24.04 и запуск HR-метрик.
# Запуск от root из папки проекта:  bash server/setup.sh
# Данные: положите версию для ПК «HR-метрики.html» в /opt — при первом запуске она загрузится и удалится.
# Повторный запуск безопасен: обновит систему, пересоберёт и перезапустит приложение.
set -euo pipefail
cd "$(dirname "$0")"
[ "$(id -u)" = 0 ] || { echo "Запустите от root: sudo bash server/setup.sh"; exit 1; }

echo "== Обновления системы и защита"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q && apt-get upgrade -yq
apt-get install -yq ca-certificates curl openssl ufw fail2ban unattended-upgrades docker.io docker-compose-v2
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

echo "== Файл подкачки (на серверах с 1 ГБ памяти — запас для сборки и обновлений)"
if ! swapon --show | grep -q . && [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "== Настройки приложения"
grep -q 'example\.ru' .env 2>/dev/null && rm .env   # незаполненный шаблон прежней версии — создаём заново
if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s|^SESSION_SECRET=.*|SESSION_SECRET=$(openssl rand -base64 48 | tr -d '\n')|" .env
fi
chmod 600 .env
if grep -qE '^DOMAIN=$' .env; then   # своего домена нет — бесплатный адрес по IP сервера, сертификат HTTPS выдаётся на него
  ip=$(curl -fsS4 https://ifconfig.me || curl -fsS4 https://api.ipify.org)
  host="${ip//./-}.sslip.io"
  sed -i "s|^DOMAIN=.*|DOMAIN=$host|; s|^BASE_URL=.*|BASE_URL=https://$host|" .env
fi
if grep -qE '^AUTH=yandex' .env && grep -qE '^(OAUTH_CLIENT_ID|OAUTH_CLIENT_SECRET|ALLOWED_DOMAINS|ADMIN_EMAILS)=$' .env; then
  echo "  Заполните server/.env (почты и ключи приложения Яндекс ID) и запустите скрипт ещё раз."
  exit 0
fi

echo "== Запуск"
mkdir -p data && chown 1000:1000 data && chmod 700 data
src=$(ls /opt/*.html 2>/dev/null | head -1 || true)
if [ -n "$src" ] && [ ! -f data/hr.sqlite ]; then   # первичные данные: приложение загрузит их при старте и удалит файл
  install -o 1000 -g 1000 -m 600 "$src" data/import.html && rm -f "$src"
fi
docker compose up -d --build
docker image prune -f >/dev/null   # старые версии программы после обновлений не копятся на диске
sleep 5; docker compose ps; docker compose logs --tail 5 app
. ./.env
echo "Готово: $BASE_URL"
[ "${AUTH:-}" = password ] && echo "Вход — логином (почтой) и паролем из «Команды», как в версии для ПК." || echo "Вход — почтой $ADMIN_EMAILS через Яндекс."

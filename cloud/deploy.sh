#!/usr/bin/env bash
# Развёртывание HR-метрик в Yandex Cloud. Подробно — в cloud/README.md.
#
#   1-й запуск:  FOLDER_ID=... DOMAIN=iway.ru ADMIN_EMAIL=you@iway.ru ./deploy.sh
#                создаёт всё, кроме функции, и печатает адрес для регистрации приложения в Яндекс ID
#   2-й запуск:  то же + OAUTH_CLIENT_ID=... OAUTH_CLIENT_SECRET=... ./deploy.sh
#                кладёт секреты в Lockbox, собирает и выкладывает функцию, включает ночные копии
#   Обновление кода — тот же 2-й запуск.
#
# Нужны: yc (после `yc init`), jq, python3, openssl. Скрипт можно запускать повторно.
set -euo pipefail
cd "$(dirname "$0")"
: "${FOLDER_ID:?Укажите FOLDER_ID — отдельный каталог в облаке только для этого приложения}"
: "${DOMAIN:?Укажите DOMAIN — домен корпоративной почты, например iway.ru}"
: "${ADMIN_EMAIL:?Укажите ADMIN_EMAIL — вашу корпоративную почту: вы станете первым администратором}"
for t in yc jq python3 openssl; do command -v $t >/dev/null || { echo "Не найден $t — установите его."; exit 1; }; done
YC="yc --folder-id $FOLDER_ID"
say(){ printf '\n== %s\n' "$*"; }
get(){ $YC "$@" --format json 2>/dev/null; }
mkdir -p dist

say "Сервисные аккаунты: hr-fn (функция), hr-gw (шлюз и таймер)"
for sa in hr-fn hr-gw; do get iam service-account get --name $sa >/dev/null || $YC iam service-account create --name $sa >/dev/null; done
FN_SA=$(get iam service-account get --name hr-fn | jq -r .id)
GW_SA=$(get iam service-account get --name hr-gw | jq -r .id)

say "База YDB (serverless)"
get ydb database get --name hr-db >/dev/null || $YC ydb database create --name hr-db --serverless >/dev/null
until [ "$(get ydb database get --name hr-db | jq -r .status)" = RUNNING ]; do echo "  жду запуска базы…"; sleep 10; done
YDB=$(get ydb database get --name hr-db | jq -r .endpoint)   # grpcs://…:2135/?database=/ru-central1/…
YDB_ENDPOINT=${YDB%%/?database=*}; YDB_DATABASE=${YDB##*database=}
$YC ydb database add-access-binding --name hr-db --role ydb.editor --service-account-id "$FN_SA" >/dev/null

say "Бакет для ночных копий: закрытый, с версиями"
BUCKET=hr-backups-$FOLDER_ID
get storage bucket get --name "$BUCKET" >/dev/null || $YC storage bucket create --name "$BUCKET" >/dev/null
$YC storage bucket update --name "$BUCKET" --versioning versioning-enabled >/dev/null
$YC resource-manager folder add-access-binding --id "$FOLDER_ID" --role storage.uploader --service-account-id "$FN_SA" >/dev/null

say "Функция и API Gateway"
get serverless function get --name hr-api >/dev/null || $YC serverless function create --name hr-api >/dev/null
FN=$(get serverless function get --name hr-api | jq -r .id)
$YC serverless function add-access-binding --id "$FN" --role functions.functionInvoker --service-account-id "$GW_SA" >/dev/null
sed -e "s/{{FUNCTION_ID}}/$FN/g; s/{{SA_ID}}/$GW_SA/g" gateway.yaml > dist/gateway.yaml
if get serverless api-gateway get --name hr-gw >/dev/null; then $YC serverless api-gateway update --name hr-gw --spec dist/gateway.yaml >/dev/null
else $YC serverless api-gateway create --name hr-gw --spec dist/gateway.yaml >/dev/null; fi
BASE_URL=https://$(get serverless api-gateway get --name hr-gw | jq -r .domain)

if [ -z "${OAUTH_CLIENT_ID:-}" ] || [ -z "${OAUTH_CLIENT_SECRET:-}" ]; then
  cat <<MSG

Готово наполовину. Зарегистрируйте приложение в Яндекс ID: https://oauth.yandex.ru/client/new
  • Название: HR-метрики i’way
  • Платформа: «Веб-сервисы», Redirect URI: $BASE_URL/api/callback
  • Доступы: «Доступ к адресу электронной почты»
Потом запустите скрипт ещё раз, добавив OAUTH_CLIENT_ID=… OAUTH_CLIENT_SECRET=… (ClientID и Client secret со страницы приложения).
MSG
  exit 0
fi

say "Секреты в Lockbox"
if ! get lockbox secret get --name hr-secrets >/dev/null; then
  $YC lockbox secret create --name hr-secrets --payload "$(jq -nc --arg c "$OAUTH_CLIENT_SECRET" --arg s "$(openssl rand -base64 48)" \
    '[{key:"OAUTH_CLIENT_SECRET",text_value:$c},{key:"SESSION_SECRET",text_value:$s}]')" >/dev/null
fi
SECRET=$(get lockbox secret get --name hr-secrets | jq -r .id)
SVER=$(get lockbox secret get --name hr-secrets | jq -r .current_version.id)
$YC lockbox secret add-access-binding --name hr-secrets --role lockbox.payloadViewer --service-account-id "$FN_SA" >/dev/null

say "Сборка и новая версия функции"
python3 build.py
$YC serverless function version create --function-id "$FN" --runtime nodejs22 --entrypoint index.handler \
  --memory 256m --execution-timeout 15s --source-path dist/function.zip --service-account-id "$FN_SA" \
  --environment "YDB_ENDPOINT=$YDB_ENDPOINT,YDB_DATABASE=$YDB_DATABASE,YDB_METADATA_CREDENTIALS=1,BASE_URL=$BASE_URL,ALLOWED_DOMAINS=$DOMAIN,ADMIN_EMAILS=$ADMIN_EMAIL,BACKUP_BUCKET=$BUCKET,OAUTH_CLIENT_ID=$OAUTH_CLIENT_ID" \
  --secret "environment-variable=OAUTH_CLIENT_SECRET,id=$SECRET,version-id=$SVER,key=OAUTH_CLIENT_SECRET" \
  --secret "environment-variable=SESSION_SECRET,id=$SECRET,version-id=$SVER,key=SESSION_SECRET" >/dev/null

say "Ночная копия базы (каждый день в 02:00 по Москве)"
get serverless trigger get --name hr-backup >/dev/null || $YC serverless trigger create timer --name hr-backup \
  --cron-expression '0 23 ? * * *' --invoke-function-id "$FN" --invoke-function-service-account-id "$GW_SA" >/dev/null

cat <<MSG

Всё готово: $BASE_URL
Войдите корпоративной почтой $ADMIN_EMAIL — вы станете администратором. Дальше — шаг «Перенос данных» в cloud/README.md.
MSG

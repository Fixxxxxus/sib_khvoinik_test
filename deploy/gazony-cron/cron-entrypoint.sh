#!/usr/bin/env bash
# Entrypoint для digest-cron: выгружает env контейнера в /etc/environment,
# чтобы cron-задача увидела DJANGO настройки, затем запускает cron и стримит лог.
set -euo pipefail

# Все переменные окружения контейнера -> /etc/environment (cron их не наследует).
printenv | grep -v '^_=' | while IFS= read -r line; do
    name="${line%%=*}"
    value="${line#*=}"
    escaped=$(printf "%s" "$value" | sed "s/'/'\\\\''/g")
    echo "${name}='${escaped}'"
done > /etc/environment

touch /var/log/gazony-digest.log
cron -L 15
exec tail -F /var/log/gazony-digest.log

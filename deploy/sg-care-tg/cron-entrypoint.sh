#!/usr/bin/env bash
# Entrypoint for digest-cron service: выгружает env контейнера в /etc/environment,
# чтобы cron-задача увидела TELEGRAM_BOT_TOKEN/TG_API_SECRET/CARE_API_BASE_URL,
# затем запускает cron в форграунде и стримит лог.
set -euo pipefail

# cron в Debian не пробрасывает переменные docker в задачу - сохраним их явно.
# Берём только нужные нам.
{
    for var in TELEGRAM_BOT_TOKEN TG_API_SECRET CARE_API_BASE_URL TZ; do
        value="${!var:-}"
        if [ -n "$value" ]; then
            # экранируем одинарные кавычки
            escaped=$(printf "%s" "$value" | sed "s/'/'\\\\''/g")
            echo "${var}='${escaped}'"
        fi
    done
} > /etc/environment

# log-файл должен существовать чтобы tail -f не падал
touch /var/log/sg-care-digest.log

# cron в Debian принимает -L 15 для подробного логирования
cron -L 15

# stream cron log to stdout, держим контейнер живым
exec tail -F /var/log/sg-care-digest.log

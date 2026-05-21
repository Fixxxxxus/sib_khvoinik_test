#!/usr/bin/env bash
# Wrapper that cron uses: cron job runs without env vars from docker,
# so we re-source /etc/environment which entrypoint populates from container env.
set -euo pipefail

# Загружаем env, который entrypoint выгружает в /etc/environment
if [ -f /etc/environment ]; then
    set -a
    . /etc/environment
    set +a
fi

cd /app
python /app/telegram_digest.py

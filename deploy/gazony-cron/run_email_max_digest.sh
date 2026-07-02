#!/usr/bin/env bash
# Еженедельный дайджест по email и MAX. Telegram НЕ трогаем: он уходит
# отдельным путём с Contabo, иначе будет двойная отправка.
set -euo pipefail
cd /app
python manage.py send_weekly_digest --channel email
python manage.py send_weekly_digest --channel max

#!/usr/bin/env bash
# Офлайн-конверсии в Метрику по yclid: раз в час досылаем заявки и оптовые
# заказы, которых счётчик не увидел из-за отказа от cookie.
set -euo pipefail
cd /app
python manage.py push_metrika_conversions --since-hours 48

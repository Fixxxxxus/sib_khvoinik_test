#!/usr/bin/env python3
"""Понедельничный пинг СММ-специалисту: предложить добавить акцию недели.

Запускается кроном (понедельник 03:00 UTC = 10:00 НСК) внутри digest-cron.
Шлёт сообщение ТОЛЬКО на CARE_PROMO_ADMIN_CHAT_ID с инлайн-кнопкой «Добавить».
"""
import os
import sys
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_CHAT_ID = os.environ.get("CARE_PROMO_ADMIN_CHAT_ID", "").strip()
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

TEXT = (
    "Если есть акции и скидки на этой неделе, давай добавим их в службу заботы.\n\n"
    "Нажмите «Добавить» и пришлите текст и/или картинку."
)


def main():
    if not ADMIN_CHAT_ID:
        print("[promo-invite] CARE_PROMO_ADMIN_CHAT_ID пуст, выходим", flush=True)
        sys.exit(0)
    keyboard = {"inline_keyboard": [[{"text": "Добавить", "callback_data": "promo_add"}]]}
    try:
        r = requests.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": int(ADMIN_CHAT_ID), "text": TEXT, "reply_markup": keyboard},
            timeout=15,
        )
        print(f"[promo-invite] sent ok={r.json().get('ok')}", flush=True)
    except Exception as e:
        print(f"[promo-invite] error: {e}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

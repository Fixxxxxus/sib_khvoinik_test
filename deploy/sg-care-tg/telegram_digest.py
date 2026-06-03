#!/usr/bin/env python3
"""
Fetches pending Telegram digest from gazony.ru API, sends messages via
Bot API, reports results back.

Runs on Thursday 05:00 UTC = 12:00 NSK via cron inside the digest-cron
container.
"""
import os
import sys
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_API_SECRET = os.environ["TG_API_SECRET"]
CARE_API_BASE = os.environ.get("CARE_API_BASE_URL", "https://gazony.ru").rstrip("/")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
CARE_HEADERS = {"X-Api-Secret": TG_API_SECRET}
WEEK = os.environ.get("WEEK", "")  # опционально, например 2026-W21


def tg_call(method, payload=None, timeout=15):
    try:
        r = requests.post(f"{TG_API}/{method}", json=payload or {}, timeout=timeout)
        return r.json()
    except Exception as e:
        print(f"[tg] {method} error: {e}", flush=True)
        return {"ok": False, "description": str(e)}


def main():
    # 1. Get pending list
    params = {}
    if WEEK:
        params["week"] = WEEK
    try:
        r = requests.get(
            f"{CARE_API_BASE}/api/care/tg/pending-digest/",
            headers=CARE_HEADERS,
            params=params,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[digest] failed to fetch pending: {e}", flush=True)
        sys.exit(1)

    items = data.get("items", [])
    week_key = data.get("week_key", "")
    print(f"[digest] week={week_key} pending={len(items)}", flush=True)
    if not items:
        print("[digest] nothing to send", flush=True)
        return

    # 2. Send
    results = []
    for item in items:
        chat_id = item["telegram_chat_id"]
        sub_id = item["subscription_id"]
        tg_text = item["tg_text"]
        manage_url = item["manage_url"]
        site_url = item.get("site_url", "https://gazony.ru")

        # Две кнопки: Сайт и Управление подпиской. Отписку убрали - она живёт
        # на странице управления подпиской.
        keyboard = {
            "inline_keyboard": [
                [{"text": "Сайт", "url": site_url}],
                [{"text": "Управление подпиской", "url": manage_url}],
            ]
        }

        res = tg_call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": tg_text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
                "reply_markup": keyboard,
            },
        )

        if res.get("ok"):
            msg_id = str(res.get("result", {}).get("message_id", ""))
            print(f"  ok sub={sub_id} msg_id={msg_id}", flush=True)
            results.append(
                {
                    "subscription_id": sub_id,
                    "week_key": week_key,
                    "status": "sent",
                    "external_id": msg_id,
                }
            )
        else:
            err = str(res.get("description", "unknown"))
            print(f"  FAIL sub={sub_id}: {err}", flush=True)
            results.append(
                {
                    "subscription_id": sub_id,
                    "week_key": week_key,
                    "status": "failed",
                    "error": err,
                }
            )

    # 3. Report
    try:
        r2 = requests.post(
            f"{CARE_API_BASE}/api/care/tg/mark-digest-sent/",
            json={"results": results},
            headers=CARE_HEADERS,
            timeout=20,
        )
        print(f"[digest] mark-sent: {r2.status_code}", flush=True)
    except Exception as e:
        print(f"[digest] mark-sent error: {e}", flush=True)

    print(
        f"[digest] done sent={sum(1 for r in results if r['status']=='sent')} "
        f"failed={sum(1 for r in results if r['status']=='failed')}",
        flush=True,
    )


if __name__ == "__main__":
    main()

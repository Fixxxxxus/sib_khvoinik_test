#!/usr/bin/env python3
"""
GitHub Actions: fetches pending Telegram digest from gazony.ru API,
sends messages via Bot API, reports results back.
Runs on Thursday 05:00 UTC = 12:00 NSK.
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
        print(f"[tg] {method} error: {e}")
        return {"ok": False, "description": str(e)}


def main():
    # 1. Get pending list
    params = {}
    if WEEK:
        params["week"] = WEEK
    try:
        r = requests.get(f"{CARE_API_BASE}/api/care/tg/pending-digest/",
                         headers=CARE_HEADERS, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[digest] failed to fetch pending: {e}")
        sys.exit(1)

    items = data.get("items", [])
    week_key = data.get("week_key", "")
    print(f"[digest] week={week_key} pending={len(items)}")
    if not items:
        print("[digest] nothing to send")
        return

    # 2. Send
    results = []
    for item in items:
        chat_id = item["telegram_chat_id"]
        sub_id = item["subscription_id"]
        tg_text = item["tg_text"]
        manage_url = item["manage_url"]
        unsub_url = item.get("unsub_url", "")
        site_url = item.get("site_url", "https://gazony.ru")
        token = item.get("token", "")

        top_row = [{"text": "Сайт", "url": site_url}]
        bottom_row = [
            {"text": "Управление", "url": manage_url},
        ]
        if unsub_url:
            bottom_row.append({"text": "Отписаться", "url": unsub_url})
        keyboard = {"inline_keyboard": [top_row, bottom_row]}

        res = tg_call("sendMessage", {
            "chat_id": chat_id,
            "text": tg_text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
            "reply_markup": keyboard,
        })

        if res.get("ok"):
            msg_id = str(res.get("result", {}).get("message_id", ""))
            print(f"  ok sub={sub_id} msg_id={msg_id}")
            results.append({
                "subscription_id": sub_id,
                "week_key": week_key,
                "status": "sent",
                "external_id": msg_id,
            })
        else:
            err = str(res.get("description", "unknown"))
            print(f"  FAIL sub={sub_id}: {err}")
            results.append({
                "subscription_id": sub_id,
                "week_key": week_key,
                "status": "failed",
                "error": err,
            })

    # 3. Report
    try:
        r2 = requests.post(
            f"{CARE_API_BASE}/api/care/tg/mark-digest-sent/",
            json={"results": results},
            headers=CARE_HEADERS,
            timeout=20,
        )
        print(f"[digest] mark-sent: {r2.status_code}")
    except Exception as e:
        print(f"[digest] mark-sent error: {e}")

    print(f"[digest] done sent={sum(1 for r in results if r['status']=='sent')} "
          f"failed={sum(1 for r in results if r['status']=='failed')}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
GitHub Actions: long-polls Telegram Bot API, handles /start <token>
and unsubscribe callbacks. Calls gazony.ru API to persist state.
Runs ~3.5 minutes to fit within a 4-minute job timeout.
"""
import os
import sys
import time
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_API_SECRET = os.environ["TG_API_SECRET"]
CARE_API_BASE = os.environ.get("CARE_API_BASE_URL", "https://gazony.ru").rstrip("/")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
CARE_HEADERS = {"X-Api-Secret": TG_API_SECRET, "Content-Type": "application/json"}


def tg_call(method, payload=None, timeout=12):
    try:
        r = requests.post(f"{TG_API}/{method}", json=payload or {}, timeout=timeout)
        return r.json()
    except Exception as e:
        print(f"[tg] {method} error: {e}")
        return {"ok": False}


def care_post(path, body, timeout=10):
    try:
        r = requests.post(f"{CARE_API_BASE}{path}", json=body,
                          headers=CARE_HEADERS, timeout=timeout)
        return r.json()
    except Exception as e:
        print(f"[care] POST {path} error: {e}")
        return {"ok": False, "error": str(e)}


def send_msg(chat_id, text, parse_mode="Markdown"):
    tg_call("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    })


def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    username = (msg.get("from") or {}).get("username", "")

    if text.startswith("/start "):
        token = text[7:].strip()
        if not token:
            send_msg(chat_id, "Пожалуйста, используйте ссылку из письма или с сайта.")
            return
        res = care_post("/api/care/tg/optin/", {
            "token": token,
            "telegram_chat_id": chat_id,
            "telegram_username": username,
        })
        if res.get("ok"):
            send_msg(chat_id,
                "Вы подключены к Службе заботы Сибирских Газонов.\n\n"
                "Каждый четверг будет приходить дайджест с задачами на неделю по вашим группам растений.\n\n"
                "Управление подпиской - кнопка внизу каждого дайджеста.")
            print(f"[poll] optin ok sub={res.get('subscription_id')} chat={chat_id}")
        else:
            send_msg(chat_id,
                "Ссылка недействительна или устарела.\n"
                "Оформите подписку заново на [gazony.ru/sluzhba-zaboty](https://gazony.ru/sluzhba-zaboty/).")
            print(f"[poll] optin fail: {res.get('error')}")

    elif text in ("/start", "/help"):
        send_msg(chat_id,
            "Бот Службы заботы «Сибирские Газоны».\n\n"
            "Чтобы подключиться, перейдите по ссылке из формы или письма с сайта "
            "[gazony.ru](https://gazony.ru/sluzhba-zaboty/).")

    elif text == "/unsubscribe":
        res = care_post("/api/care/tg/unsubscribe/", {"telegram_chat_id": chat_id})
        if res.get("ok"):
            send_msg(chat_id, "Вы отписались от дайджеста. Подписаться снова можно на сайте.")
        else:
            send_msg(chat_id, "Подписка не найдена.")


def handle_callback(cb):
    chat_id = cb["from"]["id"]
    data = (cb.get("data") or "").strip()
    callback_id = cb["id"]

    if data.startswith("unsub:"):
        token = data[6:]
        res = care_post("/api/care/tg/unsubscribe/", {
            "telegram_chat_id": chat_id,
            "token": token,
        })
        if res.get("ok"):
            tg_call("answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "Вы отписались.",
            })
            send_msg(chat_id, "Подписка отключена. Подписаться снова - на сайте.")
        else:
            tg_call("answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "Ошибка, попробуйте позже.",
            })
    else:
        tg_call("answerCallbackQuery", {"callback_query_id": callback_id})


def main():
    deadline = time.monotonic() + 360  # 6 minutes, job timeout = 10
    offset = 0
    print(f"[poll] start, deadline in 360s")
    while time.monotonic() < deadline:
        remaining = max(5, int(deadline - time.monotonic()))
        timeout = min(30, remaining - 2)
        try:
            resp = requests.post(
                f"{TG_API}/getUpdates",
                json={
                    "offset": offset,
                    "timeout": timeout,
                    "allowed_updates": ["message", "callback_query"],
                },
                timeout=timeout + 5,
            )
            updates = resp.json().get("result", [])
        except Exception as e:
            print(f"[poll] getUpdates error: {e}, retry in 5s")
            time.sleep(5)
            continue

        for u in updates:
            offset = u["update_id"] + 1
            try:
                if "message" in u:
                    handle_message(u["message"])
                elif "callback_query" in u:
                    handle_callback(u["callback_query"])
            except Exception as e:
                print(f"[poll] update handling error: {e}")

    print("[poll] done")


if __name__ == "__main__":
    main()

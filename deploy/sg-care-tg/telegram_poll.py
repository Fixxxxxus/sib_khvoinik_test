#!/usr/bin/env python3
"""
Long-poll Telegram Bot API for @sg_customer_care_bot.

Handles:
- /start <token>  - opt-in via gazony.ru, returns optional welcome payload
                    which is then immediately sent to the user and reported
                    back via mark-digest-sent (treated as the first digest).
- /start, /help   - help text
- /unsubscribe    - cancel subscription by chat_id
- callback unsub: - inline unsubscribe button from digest

Designed to run as a long-living docker service (restart: unless-stopped).
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

POLL_TIMEOUT = int(os.environ.get("TG_POLL_TIMEOUT", "50"))  # long-poll seconds
PROMO_ADMIN_CHAT_ID = os.environ.get("CARE_PROMO_ADMIN_CHAT_ID", "").strip()


def tg_call(method, payload=None, timeout=15):
    try:
        r = requests.post(f"{TG_API}/{method}", json=payload or {}, timeout=timeout)
        return r.json()
    except Exception as e:
        print(f"[tg] {method} error: {e}", flush=True)
        return {"ok": False}


def care_post(path, body, timeout=15):
    try:
        r = requests.post(
            f"{CARE_API_BASE}{path}",
            json=body,
            headers=CARE_HEADERS,
            timeout=timeout,
        )
        return r.json()
    except Exception as e:
        print(f"[care] POST {path} error: {e}", flush=True)
        return {"ok": False, "error": str(e)}


def care_get(path, timeout=15):
    try:
        r = requests.get(f"{CARE_API_BASE}{path}", headers=CARE_HEADERS, timeout=timeout)
        return r.json()
    except Exception as e:
        print(f"[care] GET {path} error: {e}", flush=True)
        return {"ok": False, "error": str(e)}


def care_post_multipart(path, data, files, timeout=60):
    """POST multipart в Django. Заголовок Content-Type ставит requests сам."""
    headers = {"X-Api-Secret": TG_API_SECRET}
    try:
        r = requests.post(
            f"{CARE_API_BASE}{path}", data=data, files=files, headers=headers, timeout=timeout
        )
        return r.json()
    except Exception as e:
        print(f"[care] MP POST {path} error: {e}", flush=True)
        return {"ok": False, "error": str(e)}


def tg_get_file_bytes(file_id, timeout=30):
    """getFile + скачивание байтов картинки по токену бота. None при сбое."""
    try:
        meta = requests.post(f"{TG_API}/getFile", json={"file_id": file_id}, timeout=timeout).json()
        if not meta.get("ok"):
            return None
        file_path = meta["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"[promo] getFile failed: {e}", flush=True)
        return None


def send_promo_preview(chat_id, preview):
    """Отправляет специалисту превью акции с кнопками Подтвердить/Изменить."""
    text = preview.get("text") or ""
    image_url = preview.get("image_url")
    caption = "Так будет выглядеть акция в дайджесте:\n\n" + text if text else "Картинка акции:"
    keyboard = {
        "inline_keyboard": [[
            {"text": "Подтвердить", "callback_data": "promo_confirm"},
            {"text": "Изменить", "callback_data": "promo_edit"},
        ]]
    }
    if image_url:
        tg_call("sendPhoto", {"chat_id": chat_id, "photo": image_url, "caption": caption, "reply_markup": keyboard})
    else:
        send_msg(chat_id, caption, reply_markup=keyboard)


def send_msg(chat_id, text, parse_mode="Markdown", reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return tg_call("sendMessage", payload)


def send_welcome_and_report(chat_id, subscription_id, welcome):
    """
    Send welcome message right after opt-in and report it as the first digest
    via /api/care/tg/mark-digest-sent/ so Django marks the current week as
    already delivered.
    """
    tg_text = welcome.get("tg_text") or ""
    week_key = welcome.get("week_key") or ""
    site_url = welcome.get("site_url") or "https://gazony.ru"
    manage_url = welcome.get("manage_url") or ""
    unsub_url = welcome.get("unsub_url") or ""

    top_row = [{"text": "Сайт", "url": site_url}]
    bottom_row = []
    if manage_url:
        bottom_row.append({"text": "Управление", "url": manage_url})
    if unsub_url:
        bottom_row.append({"text": "Отписаться", "url": unsub_url})

    rows = [top_row]
    if bottom_row:
        rows.append(bottom_row)
    keyboard = {"inline_keyboard": rows}

    if not tg_text:
        print(f"[welcome] empty tg_text sub={subscription_id}, skip", flush=True)
        return

    res = send_msg(chat_id, tg_text, parse_mode="Markdown", reply_markup=keyboard)
    if not res.get("ok"):
        err = str(res.get("description", "unknown"))
        print(f"[welcome] sendMessage FAIL sub={subscription_id}: {err}", flush=True)
        if week_key:
            care_post(
                "/api/care/tg/mark-digest-sent/",
                {
                    "results": [
                        {
                            "subscription_id": subscription_id,
                            "week_key": week_key,
                            "status": "failed",
                            "error": err,
                        }
                    ]
                },
            )
        return

    msg_id = str(res.get("result", {}).get("message_id", ""))
    print(f"[welcome] ok sub={subscription_id} msg_id={msg_id}", flush=True)
    if not week_key:
        # без week_key Django не сможет атрибутировать запись
        return
    care_post(
        "/api/care/tg/mark-digest-sent/",
        {
            "results": [
                {
                    "subscription_id": subscription_id,
                    "week_key": week_key,
                    "status": "sent",
                    "external_id": msg_id,
                }
            ]
        },
    )


def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    username = (msg.get("from") or {}).get("username", "")

    from_id = (msg.get("from") or {}).get("id")
    # Промо-контент от СММ: только этот chat_id, только когда ждём контент.
    if PROMO_ADMIN_CHAT_ID and str(from_id) == PROMO_ADMIN_CHAT_ID:
        cur = care_get("/api/care/tg/promo/current/")
        if cur.get("status") == "awaiting_content":
            photos = msg.get("photo") or []
            content_text = (msg.get("caption") or msg.get("text") or "").strip()
            data = {"telegram_chat_id": from_id, "text": content_text, "tg_file_id": ""}
            files = {}
            photo_download_failed = False
            if photos:
                file_id = photos[-1]["file_id"]  # самый крупный размер
                data["tg_file_id"] = file_id
                img = tg_get_file_bytes(file_id)
                if img is not None:
                    files["image"] = ("promo.jpg", img, "image/jpeg")
                else:
                    photo_download_failed = True
            res = care_post_multipart("/api/care/tg/promo/content/", data, files)
            if res.get("ok"):
                send_promo_preview(from_id, res.get("preview") or {"text": content_text})
                if photo_download_failed:
                    send_msg(
                        from_id,
                        "Не удалось скачать картинку из Telegram, акция сохранена без неё. "
                        "Пришлите фото ещё раз или добавьте его вручную.",
                    )
            else:
                send_msg(from_id, "Не получилось сохранить акцию, попробуйте ещё раз.")
            return

    if text.startswith("/start "):
        token = text[7:].strip()
        if not token:
            send_msg(chat_id, "Пожалуйста, используйте ссылку из письма или с сайта.")
            return
        res = care_post(
            "/api/care/tg/optin/",
            {
                "token": token,
                "telegram_chat_id": chat_id,
                "telegram_username": username,
            },
        )
        if res.get("ok"):
            subscription_id = res.get("subscription_id")
            welcome = res.get("welcome")
            # chat_id в лог не пишем: идентификатор подписчика в Telegram - ПДн,
            # а логи лежат на зарубежном VPS; для разбора достаточно sub=
            print(
                f"[poll] optin ok sub={subscription_id} "
                f"welcome={'yes' if welcome else 'no'}",
                flush=True,
            )
            if welcome:
                # новый формат: первое сообщение уже подготовил Django
                send_welcome_and_report(chat_id, subscription_id, welcome)
            else:
                # fallback на старый текст подтверждения
                send_msg(
                    chat_id,
                    "Вы подключены к Службе заботы Сибирских Газонов.\n\n"
                    "Каждый четверг будет приходить дайджест с задачами на неделю "
                    "по вашим группам растений.\n\n"
                    "Управление подпиской - кнопка внизу каждого дайджеста.",
                )
        else:
            send_msg(
                chat_id,
                "Ссылка недействительна или устарела.\n"
                "Оформите подписку заново на "
                "[gazony.ru/sluzhba-zaboty](https://gazony.ru/sluzhba-zaboty/).",
            )
            print(f"[poll] optin fail: {res.get('error')}", flush=True)

    elif text in ("/start", "/help"):
        send_msg(
            chat_id,
            "Бот Службы заботы «Сибирские Газоны».\n\n"
            "Чтобы подключиться, перейдите по ссылке из формы или письма с сайта "
            "[gazony.ru](https://gazony.ru/sluzhba-zaboty/).",
        )

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
        res = care_post(
            "/api/care/tg/unsubscribe/",
            {"telegram_chat_id": chat_id, "token": token},
        )
        if res.get("ok"):
            tg_call(
                "answerCallbackQuery",
                {"callback_query_id": callback_id, "text": "Вы отписались."},
            )
            send_msg(chat_id, "Подписка отключена. Подписаться снова - на сайте.")
        else:
            tg_call(
                "answerCallbackQuery",
                {"callback_query_id": callback_id, "text": "Ошибка, попробуйте позже."},
            )
    elif data == "promo_add":
        if not (PROMO_ADMIN_CHAT_ID and str(chat_id) == PROMO_ADMIN_CHAT_ID):
            tg_call("answerCallbackQuery", {"callback_query_id": callback_id})
            return
        care_post("/api/care/tg/promo/start/", {"telegram_chat_id": chat_id})
        tg_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "Жду акцию"})
        # Убираем кнопку и подсказываем прислать контент.
        msg_id = (cb.get("message") or {}).get("message_id")
        if msg_id:
            tg_call("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": msg_id, "reply_markup": {"inline_keyboard": []}})
        send_msg(chat_id, "Пришлите текст акции и/или картинку одним сообщением.")

    elif data == "promo_confirm":
        if not (PROMO_ADMIN_CHAT_ID and str(chat_id) == PROMO_ADMIN_CHAT_ID):
            tg_call("answerCallbackQuery", {"callback_query_id": callback_id})
            return
        res = care_post("/api/care/tg/promo/confirm/", {"telegram_chat_id": chat_id})
        if res.get("ok"):
            tg_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "Подтверждено"})
            send_msg(chat_id, "Готово, акция уйдёт подписчикам в ближайшей рассылке.")
        elif res.get("error") == "already_sent":
            tg_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "Рассылка уже ушла"})
        else:
            tg_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "Ошибка, попробуйте позже"})

    elif data == "promo_edit":
        if not (PROMO_ADMIN_CHAT_ID and str(chat_id) == PROMO_ADMIN_CHAT_ID):
            tg_call("answerCallbackQuery", {"callback_query_id": callback_id})
            return
        res = care_post("/api/care/tg/promo/edit/", {"telegram_chat_id": chat_id})
        if res.get("ok"):
            tg_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "Пришлите новый вариант"})
            send_msg(chat_id, "Пришлите новый текст акции и/или картинку.")
        elif res.get("error") == "already_sent":
            tg_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "Рассылка уже ушла, изменить нельзя"})
        else:
            tg_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "Ошибка, попробуйте позже"})

    else:
        tg_call("answerCallbackQuery", {"callback_query_id": callback_id})


def main():
    offset = 0
    print(
        f"[poll] start, long-poll timeout={POLL_TIMEOUT}s, "
        f"care_api={CARE_API_BASE}",
        flush=True,
    )
    while True:
        try:
            resp = requests.post(
                f"{TG_API}/getUpdates",
                json={
                    "offset": offset,
                    "timeout": POLL_TIMEOUT,
                    "allowed_updates": ["message", "callback_query"],
                },
                timeout=POLL_TIMEOUT + 10,
            )
            updates = resp.json().get("result", [])
        except Exception as e:
            print(f"[poll] getUpdates error: {e}, retry in 5s", flush=True)
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
                print(f"[poll] update handling error: {e}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[poll] interrupted", flush=True)
        sys.exit(0)

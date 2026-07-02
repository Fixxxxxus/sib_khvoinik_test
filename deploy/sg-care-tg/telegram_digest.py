#!/usr/bin/env python3
"""
Fetches pending Telegram digest from gazony.ru API, sends messages via
Bot API, reports results back.

Runs on Thursday 05:00 UTC = 12:00 NSK via cron inside the digest-cron
container.
"""
import json
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


def tg_send_album(chat_id, image_urls, timeout=120):
    """Заливает альбом карточек в Telegram МУЛЬТИПАРТОМ (attach://), а не по URL.

    Метод `media: <url>` перекладывает скачивание на серверы Telegram и
    периодически падает с WEBPAGE_CURL_FAILED (media group атомарен - валится
    весь альбом). Поэтому качаем байты сами и отдаём файлами. Best-effort:
    любой сбой возвращает {'ok': False, ...} и не должен ронять текст дайджеста.
    """
    urls = [u for u in (image_urls or []) if u][:10]  # лимит Telegram: 2..10
    if not urls:
        return {"ok": False, "description": "no images"}

    files = {}
    media = []
    for i, u in enumerate(urls):
        try:
            r = requests.get(u, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"[album] fetch failed {u}: {e}", flush=True)
            continue
        key = f"photo{i}"
        files[key] = (f"{key}.png", r.content, "image/png")
        media.append({"type": "photo", "media": f"attach://{key}"})

    if not media:
        return {"ok": False, "description": "no images fetched"}
    try:
        if len(media) == 1:
            # sendMediaGroup требует 2..10 элементов; одну картинку шлём sendPhoto.
            only_key = media[0]["media"].split("://", 1)[1]
            r = requests.post(
                f"{TG_API}/sendPhoto",
                data={"chat_id": chat_id},
                files={"photo": files[only_key]},
                timeout=timeout,
            )
        else:
            r = requests.post(
                f"{TG_API}/sendMediaGroup",
                data={"chat_id": chat_id, "media": json.dumps(media)},
                files=files,
                timeout=timeout,
            )
        return r.json()
    except Exception as e:
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
            timeout=120,
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

        # Альбом карточек (если есть) - отправляем до текстового сообщения.
        # Мультипарт-заливкой (attach://), а не по URL: так Telegram не скачивает
        # картинки сам и не падает с WEBPAGE_CURL_FAILED. Best-effort.
        images = item.get("images") or []
        promo = item.get("promo_image")
        album_urls = list(images)
        if promo:
            album_urls.append(promo)
        if album_urls:
            album = tg_send_album(chat_id, album_urls)
            if not album.get("ok"):
                print(f"sendMediaGroup failed for {sub_id}: {album.get('description')}", flush=True)

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

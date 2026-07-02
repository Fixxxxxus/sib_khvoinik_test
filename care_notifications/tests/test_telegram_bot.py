"""Тесты TelegramBotClient: альбом карточек через sendMediaGroup и его вплетение
в send_digest. Сетевые вызовы заглушены monkeypatch'ем на `requests.post`.

Контракт альбома повторяет MAX: card_image_urls + promo, best-effort - сбой
альбома не мешает уйти тексту дайджеста.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _make_payload(**over):
    """Минимальный DigestPayload для тестов send_digest (без похода в БД)."""
    from care_notifications.digest import DigestFooter, DigestPayload

    footer = DigestFooter(
        site_url="https://gazony.ru/care/",
        telegram_url="https://t.me/x",
        max_url="https://max.ru/x",
        manage_url="https://gazony.ru/care/manage/?t=tok",
        unsubscribe_url="https://gazony.ru/care/unsub/?t=tok",
    )
    base = dict(
        week_key="2026-W27",
        subject="Тест",
        hero_image_url=None,
        hero_image_path=None,
        hero_title="Заголовок",
        hero_text="Текст",
        blocks=[],
        footer=footer,
        season_label="Лето",
        card_image_urls=[],
        promo_image_url=None,
    )
    base.update(over)
    return DigestPayload(**base)


def test_send_media_group_no_token_returns_error(monkeypatch):
    """Без TELEGRAM_BOT_TOKEN альбом не падает, а возвращает ok=False."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    from care_notifications.telegram_bot import TelegramBotClient

    res = TelegramBotClient().send_media_group(chat_id=1, image_urls=["https://x/a.png"])
    assert res["ok"] is False
    assert "TOKEN" in res["error"]


def test_send_media_group_empty_urls_returns_error(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    from care_notifications.telegram_bot import TelegramBotClient

    res = TelegramBotClient().send_media_group(chat_id=1, image_urls=[])
    assert res["ok"] is False


def test_send_media_group_single_url_uses_send_photo_by_url(monkeypatch):
    """Одна картинка: sendMediaGroup невалиден (нужно 2..10), шлём через sendPhoto по URL."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"ok": True, "result": {"message_id": 555}}

    def _fake_post(url, json=None, data=None, files=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp()

    import care_notifications.telegram_bot as mod
    monkeypatch.setattr(mod.requests, "post", _fake_post)

    res = mod.TelegramBotClient().send_media_group(chat_id=42, image_urls=["https://x/a.png"])
    assert res == {"ok": True, "message_id": 555, "error": ""}
    assert captured["url"].endswith("/sendPhoto")
    assert captured["json"]["chat_id"] == 42
    assert captured["json"]["photo"] == "https://x/a.png"


def test_send_media_group_multi_url_uses_media_group(monkeypatch):
    """Несколько картинок: один sendMediaGroup с media=[{type:photo, media:url}]."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"ok": True, "result": [{"message_id": 900}, {"message_id": 901}]}

    def _fake_post(url, json=None, data=None, files=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp()

    import care_notifications.telegram_bot as mod
    monkeypatch.setattr(mod.requests, "post", _fake_post)

    urls = ["https://x/a.png", "https://x/b.png", "https://x/c.png"]
    res = mod.TelegramBotClient().send_media_group(chat_id=7, image_urls=urls)
    assert res["ok"] is True
    assert res["message_id"] == 900
    assert captured["url"].endswith("/sendMediaGroup")
    media = captured["json"]["media"]
    assert [m["media"] for m in media] == urls
    assert all(m["type"] == "photo" for m in media)


def test_send_digest_sends_card_album_then_text(monkeypatch):
    """send_digest должен послать альбом (карточки + промо) и затем текст."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    from care_notifications.telegram_bot import TelegramBotClient

    client = TelegramBotClient()
    calls = {}

    def _fake_media_group(chat_id, image_urls):
        calls["album"] = (chat_id, list(image_urls))
        return {"ok": True, "message_id": 1, "error": ""}

    def _fake_send_message(chat_id, text, **kw):
        calls["text"] = (chat_id, text)
        return {"ok": True, "message_id": 2, "error": ""}

    monkeypatch.setattr(client, "send_media_group", _fake_media_group)
    monkeypatch.setattr(client, "send_message", _fake_send_message)

    sub = SimpleNamespace(id=1, telegram_chat_id=333611867)
    payload = _make_payload(
        card_image_urls=["https://x/c1.png", "https://x/c2.png"],
        promo_image_url="https://x/promo.png",
    )
    res = client.send_digest(sub, payload)

    assert calls["album"][0] == 333611867
    assert calls["album"][1] == ["https://x/c1.png", "https://x/c2.png", "https://x/promo.png"]
    assert calls["text"][0] == 333611867
    assert res["ok"] is True
    assert res["message_id"] == 2


def test_send_digest_album_failure_does_not_block_text(monkeypatch):
    """Любой сбой альбома (в т.ч. исключение) не мешает уйти тексту дайджеста."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    from care_notifications.telegram_bot import TelegramBotClient

    client = TelegramBotClient()
    calls = {}

    def _boom(chat_id, image_urls):
        raise RuntimeError("album exploded")

    def _fake_send_message(chat_id, text, **kw):
        calls["text"] = (chat_id, text)
        return {"ok": True, "message_id": 2, "error": ""}

    monkeypatch.setattr(client, "send_media_group", _boom)
    monkeypatch.setattr(client, "send_message", _fake_send_message)

    sub = SimpleNamespace(id=1, telegram_chat_id=333611867)
    payload = _make_payload(card_image_urls=["https://x/c1.png"], promo_image_url=None)
    res = client.send_digest(sub, payload)

    assert calls.get("text") is not None
    assert res["ok"] is True

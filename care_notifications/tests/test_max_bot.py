"""Тесты MaxBotClient: токен из env, конвертация клавиатуры, no-op без токена.

Сетевые вызовы заглушены через monkeypatch на `requests.request`, чтобы тесты
не лезли наружу и работали без реального MAX_BOT_TOKEN.
"""

from __future__ import annotations

import json

import pytest


def test_no_token_send_message_returns_error(monkeypatch):
    """Без MAX_BOT_TOKEN send_message не падает, возвращает {'ok': False, error: '...'}."""
    monkeypatch.delenv("MAX_BOT_TOKEN", raising=False)
    from care_notifications.max_bot import MaxBotClient

    client = MaxBotClient()
    res = client.send_message(chat_id="123", text="hello")
    assert res["ok"] is False
    assert "MAX_BOT_TOKEN" in res["error"]


def test_convert_reply_markup_to_attachments():
    """TG-подобная клавиатура должна превращаться в MAX inline_keyboard attachment."""
    from care_notifications.max_bot import MaxBotClient

    reply_markup = {
        "inline_keyboard": [
            [{"text": "Сайт", "url": "https://gazony.ru"}],
            [
                {"text": "Управление", "url": "https://gazony.ru/care/manage/?t=..."},
                {"text": "Отписаться", "callback_data": "unsub:abc123"},
            ],
        ]
    }
    out = MaxBotClient._convert_reply_markup_to_attachments(reply_markup)
    assert isinstance(out, list) and len(out) == 1
    att = out[0]
    assert att["type"] == "inline_keyboard"
    rows = att["payload"]["buttons"]
    assert len(rows) == 2
    assert rows[0][0] == {"type": "link", "text": "Сайт", "url": "https://gazony.ru"}
    assert rows[1][1]["type"] == "callback"
    assert rows[1][1]["payload"] == "unsub:abc123"


def test_convert_reply_markup_none():
    from care_notifications.max_bot import MaxBotClient
    assert MaxBotClient._convert_reply_markup_to_attachments(None) is None
    assert MaxBotClient._convert_reply_markup_to_attachments({"inline_keyboard": []}) is None


def test_send_message_with_token_calls_api(monkeypatch):
    """С токеном идёт POST /messages: получатель chat_id - в query, текст - в теле.

    MAX (в отличие от Telegram) требует chat_id/user_id именно query-параметром
    URL, а не в JSON-теле: тело с chat_id отдаёт 400 'Unknown recipient'.
    """
    monkeypatch.setenv("MAX_BOT_TOKEN", "test-token-xyz")

    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"message": {"id": "msg-42"}}

    def _fake_request(method, url, json=None, headers=None, timeout=None, params=None):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["params"] = params
        return _Resp()

    import care_notifications.max_bot as mod
    monkeypatch.setattr(mod.requests, "request", _fake_request)

    client = mod.MaxBotClient()
    res = client.send_message(
        chat_id="42",
        text="hi",
        reply_markup={"inline_keyboard": [[{"text": "go", "url": "https://x"}]]},
    )
    assert res == {"ok": True, "message_id": "msg-42", "error": ""}
    assert captured["url"] == "https://platform-api.max.ru/messages"
    assert captured["method"] == "POST"
    assert captured["headers"]["Authorization"] == "test-token-xyz"
    # получатель - в query-параметрах, НЕ в теле
    assert captured["params"]["chat_id"] == "42"
    assert "chat_id" not in (captured["json"] or {})
    assert captured["json"]["text"] == "hi"
    assert captured["json"]["format"] == "markdown"
    assert captured["json"]["attachments"][0]["type"] == "inline_keyboard"


def test_send_message_api_error(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "tok")

    class _Resp:
        status_code = 400

        def json(self):
            return {"message": "chat not found"}

    def _fake_request(*a, **kw):
        return _Resp()

    import care_notifications.max_bot as mod
    monkeypatch.setattr(mod.requests, "request", _fake_request)

    res = mod.MaxBotClient().send_message(chat_id="0", text="x")
    assert res["ok"] is False
    assert "chat not found" in res["error"]


@pytest.mark.django_db
def test_max_webhook_bot_started_optin(client, monkeypatch):
    """Deep-link `?start=<token>` приходит как update_type=bot_started с токеном
    в update['payload'] и chat_id на верхнем уровне - webhook должен сделать opt-in.

    Форма апдейта взята из реального ответа MAX (платформа OneMe Bot API).
    """
    from care_notifications import views
    from care_notifications.models import CareSubscription

    monkeypatch.setattr(views, "_MAX_WEBHOOK_SECRET", "secret123")
    # не лезем в сеть на ответном сообщении и не шлём приветственный дайджест
    monkeypatch.setattr(
        "care_notifications.max_bot.MaxBotClient.send_message",
        lambda self, chat_id, text, **kw: {"ok": True, "message_id": "1", "error": ""},
    )
    monkeypatch.setattr(views, "_max_send_welcome_digest", lambda sub: None)

    sub = CareSubscription.objects.create(email="a@b.c", preferred_channel="max")
    update = {
        "update_type": "bot_started",
        "timestamp": 1781151778278,
        "chat_id": 303629461,
        "user": {"user_id": 21535639, "name": "Станислав", "is_bot": False},
        "user_locale": "ru",
        "payload": sub.token,
    }
    resp = client.post(
        "/api/care/max/webhook/secret123/",
        data=json.dumps(update),
        content_type="application/json",
    )
    assert resp.status_code == 200
    sub.refresh_from_db()
    assert sub.max_chat_id == 303629461
    assert sub.max_opted_in_at is not None
    assert sub.active is True

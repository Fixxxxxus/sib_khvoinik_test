"""Тесты MaxBotClient: токен из env, конвертация клавиатуры, no-op без токена.

Сетевые вызовы заглушены через monkeypatch на `requests.request`, чтобы тесты
не лезли наружу и работали без реального MAX_BOT_TOKEN.
"""

from __future__ import annotations

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
    """С токеном идёт реальный POST /messages с правильным заголовком Authorization."""
    monkeypatch.setenv("MAX_BOT_TOKEN", "test-token-xyz")

    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"message": {"id": "msg-42"}}

    def _fake_request(method, url, json=None, headers=None, timeout=None):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
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
    assert captured["json"]["chat_id"] == "42"
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

#!/usr/bin/env python3
"""Тонкий клиент Yandex Webmaster API v4 для gazony.ru.

Автономный скрипт (без Django). Секреты читаются из .env в корне проекта.
API маленький и плоский: один OAuth-токен в заголовке Authorization, два
стартовых вызова за user_id/host_id, дальше прямые GET/POST.

OAuth (authorization code flow):
  1) python scripts/yandex_webmaster.py auth-url      -> печатает ссылку
  2) открыть ссылку, «Разрешить», скопировать код подтверждения
  3) python scripts/yandex_webmaster.py auth <код>    -> меняет код на токен,
     дописывает YANDEX_WEBMASTER_ACCESS_TOKEN/REFRESH в .env

Команды после авторизации:
  whoami                       user_id + список хостов
  queries [--days N]           популярные поисковые запросы хоста
  diag                         сводка/диагностика хоста (summary)
  important                    важные URL хоста (что в индексе и проблемы)
  quota                        суточная квота переобхода
  recrawl <url> [<url> ...]    отправить страницы на переобход
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.webmaster.yandex.net/v4"
OAUTH_AUTHORIZE = "https://oauth.yandex.ru/authorize"
OAUTH_TOKEN = "https://oauth.yandex.ru/token"
# Redirect приложения на oauth.yandex.ru: код подтверждения показывается на странице.
REDIRECT_URI = "https://oauth.yandex.ru/verification_code"

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


# --------------------------------------------------------------------------- env
def read_env() -> dict[str, str]:
    data: dict[str, str] = {}
    if not ENV_PATH.exists():
        return data
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        data[k.strip()] = v.strip()
    return data


def set_env(updates: dict[str, str]) -> None:
    """Обновить/добавить ключи в .env, не трогая остальное."""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


# -------------------------------------------------------------------------- http
def _request(url: str, *, token: str | None = None, method: str = "GET",
             data: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    hdrs = dict(headers or {})
    if token:
        hdrs["Authorization"] = f"OAuth {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise SystemExit(f"HTTP {e.code} {url}\n{body}")
    return json.loads(body) if body else {}


# ------------------------------------------------------------------------- oauth
def auth_url(client_id: str) -> str:
    q = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
    })
    return f"{OAUTH_AUTHORIZE}?{q}"


def exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    payload = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    return _request(
        OAUTH_TOKEN, method="POST", data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


# ------------------------------------------------------------------------ client
class YandexWebmaster:
    def __init__(self, token: str):
        self.token = token
        self._user_id: int | None = None

    def user_id(self) -> int:
        if self._user_id is None:
            self._user_id = _request(f"{BASE}/user", token=self.token)["user_id"]
        return self._user_id

    def hosts(self) -> list[dict]:
        uid = self.user_id()
        return _request(f"{BASE}/user/{uid}/hosts", token=self.token).get("hosts", [])

    def _host_id(self, want: str = "gazony.ru") -> str:
        for h in self.hosts():
            if want in (h.get("ascii_host_url") or h.get("unicode_host_url") or ""):
                return h["host_id"]
        raise SystemExit(f"Хост {want} не найден среди подтверждённых. Список: hosts")

    def popular_queries(self, days: int = 28) -> dict:
        uid, hid = self.user_id(), self._host_id()
        q = urllib.parse.urlencode({
            "order_by": "TOTAL_SHOWS",
            "query_indicator": ["TOTAL_SHOWS", "TOTAL_CLICKS", "AVG_SHOW_POSITION"],
        }, doseq=True)
        return _request(
            f"{BASE}/user/{uid}/hosts/{hid}/search-queries/popular?{q}", token=self.token)

    def summary(self) -> dict:
        uid, hid = self.user_id(), self._host_id()
        return _request(f"{BASE}/user/{uid}/hosts/{hid}/summary", token=self.token)

    def important_urls(self) -> dict:
        uid, hid = self.user_id(), self._host_id()
        return _request(f"{BASE}/user/{uid}/hosts/{hid}/important-urls", token=self.token)

    def recrawl_quota(self) -> dict:
        uid, hid = self.user_id(), self._host_id()
        return _request(f"{BASE}/user/{uid}/hosts/{hid}/recrawl/quota", token=self.token)

    def recrawl(self, url: str) -> dict:
        uid, hid = self.user_id(), self._host_id()
        payload = json.dumps({"url": url}).encode()
        return _request(
            f"{BASE}/user/{uid}/hosts/{hid}/recrawl/queue", token=self.token,
            method="POST", data=payload, headers={"Content-Type": "application/json"})


# --------------------------------------------------------------------------- cli
def _token_or_die(env: dict[str, str]) -> str:
    tok = env.get("YANDEX_WEBMASTER_ACCESS_TOKEN", "")
    if not tok:
        raise SystemExit("Нет токена. Сначала: auth-url -> auth <код>")
    return tok


def main() -> None:
    p = argparse.ArgumentParser(description="Yandex Webmaster API клиент для gazony.ru")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth-url")
    pa = sub.add_parser("auth")
    pa.add_argument("code")
    sub.add_parser("whoami")
    pq = sub.add_parser("queries")
    pq.add_argument("--days", type=int, default=28)
    sub.add_parser("diag")
    sub.add_parser("important")
    sub.add_parser("quota")
    pr = sub.add_parser("recrawl")
    pr.add_argument("urls", nargs="+")
    args = p.parse_args()

    env = read_env()

    if args.cmd == "auth-url":
        cid = env.get("YANDEX_WEBMASTER_CLIENT_ID", "")
        if not cid:
            raise SystemExit("Нет YANDEX_WEBMASTER_CLIENT_ID в .env")
        print(auth_url(cid))
        return

    if args.cmd == "auth":
        cid = env.get("YANDEX_WEBMASTER_CLIENT_ID", "")
        secret = env.get("YANDEX_WEBMASTER_CLIENT_SECRET", "")
        if not cid or not secret:
            raise SystemExit("Нужны CLIENT_ID и CLIENT_SECRET в .env")
        tok = exchange_code(cid, secret, args.code)
        updates = {"YANDEX_WEBMASTER_ACCESS_TOKEN": tok["access_token"]}
        if tok.get("refresh_token"):
            updates["YANDEX_WEBMASTER_REFRESH_TOKEN"] = tok["refresh_token"]
        wm = YandexWebmaster(tok["access_token"])
        updates["YANDEX_WEBMASTER_USER_ID"] = str(wm.user_id())
        set_env(updates)
        print(f"OK, токен сохранён. user_id={updates['YANDEX_WEBMASTER_USER_ID']}, "
              f"истекает через ~{tok.get('expires_in', '?')} сек")
        return

    wm = YandexWebmaster(_token_or_die(env))
    if args.cmd == "whoami":
        out = {"user_id": wm.user_id(), "hosts": [
            {"host_id": h.get("host_id"),
             "url": h.get("ascii_host_url"),
             "verified": h.get("verified")} for h in wm.hosts()]}
    elif args.cmd == "queries":
        out = wm.popular_queries(args.days)
    elif args.cmd == "diag":
        out = wm.summary()
    elif args.cmd == "important":
        out = wm.important_urls()
    elif args.cmd == "quota":
        out = wm.recrawl_quota()
    elif args.cmd == "recrawl":
        out = {u: wm.recrawl(u) for u in args.urls}
    else:  # pragma: no cover
        p.error("неизвестная команда")
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()

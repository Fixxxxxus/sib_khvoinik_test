#!/usr/bin/env python3
"""Тонкий клиент Yandex Metrika API для счётчика gazony.ru.

Автономный скрипт (без Django), по образцу scripts/yandex_webmaster.py.
Секреты читаются из .env в корне проекта:
  YANDEX_METRIKA_ACCESS_TOKEN  - OAuth-токен с правом metrika:read
  YANDEX_METRIKA_COUNTER_ID    - id счётчика (по умолчанию 108722541)

Два API: Management (счётчики, цели) и Reports (stat/v1/data).
Даты - как у Метрики: YYYY-MM-DD, today, yesterday, NdaysAgo.

Команды:
  counters                         счётчики, доступные токену
  goals                            цели счётчика (id, имя, условие)
  summary  [--from D] [--to D]     визиты / посетители / отказы / глубина / время
  sources  [--from D] [--to D]     трафик по каналам (lastTrafficSource)
  pages    [--from D] [--to D] [--limit N]   топ страниц входа
  goal <id|подстрока имени> [--from D] [--to D]   конверсии цели, разрез по каналам
  goals-report [--from D] [--to D] все цели: достижения и конверсия за период
  raw --metrics M [--dimensions D] [--filters F] [--from D] [--to D] [--limit N]
                                   произвольный запрос к stat/v1/data, печатает JSON

По умолчанию период - последние 30 дней (--from 30daysAgo --to yesterday).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MANAGEMENT = "https://api-metrika.yandex.net/management/v1"
STAT = "https://api-metrika.yandex.net/stat/v1/data"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
DEFAULT_COUNTER = "108722541"


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


# -------------------------------------------------------------------------- http
def _request(url: str, token: str, params: dict | None = None) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    req = urllib.request.Request(url, headers={"Authorization": f"OAuth {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise SystemExit(f"HTTP {e.code} {url}\n{body}")
    return json.loads(body) if body else {}


# ------------------------------------------------------------------------ client
class YandexMetrika:
    def __init__(self, token: str, counter_id: str):
        self.token = token
        self.counter_id = counter_id

    # --- management
    def counters(self) -> list[dict]:
        return _request(f"{MANAGEMENT}/counters", self.token).get("counters", [])

    def goals(self) -> list[dict]:
        return _request(f"{MANAGEMENT}/counter/{self.counter_id}/goals", self.token).get("goals", [])

    def find_goal(self, needle: str) -> dict:
        goals = self.goals()
        if needle.isdigit():
            for g in goals:
                if str(g["id"]) == needle:
                    return g
        low = needle.lower()
        hits = [g for g in goals if low in g["name"].lower()]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise SystemExit(f"Цель «{needle}» не найдена. Список: goals")
        names = "\n".join(f"  {g['id']}  {g['name']}" for g in hits)
        raise SystemExit(f"Под «{needle}» подходит несколько целей, уточни id:\n{names}")

    # --- reports
    def data(self, metrics: str, dimensions: str = "", date1: str = "30daysAgo",
             date2: str = "yesterday", filters: str = "", limit: int = 50,
             sort: str | None = None) -> dict:
        params: dict = {
            "ids": self.counter_id,
            "metrics": metrics,
            "date1": date1,
            "date2": date2,
            "limit": limit,
            "accuracy": "full",
        }
        if dimensions:
            params["dimensions"] = dimensions
        if filters:
            params["filters"] = filters
        params["sort"] = sort or f"-{metrics.split(',')[0]}"
        return _request(STAT, self.token, params)


# ------------------------------------------------------------------------ output
def _rows(report: dict) -> list[tuple[list[str], list[float]]]:
    out = []
    for row in report.get("data", []):
        dims = [d.get("name") or d.get("id") or "-" for d in row.get("dimensions", [])]
        out.append((dims, row.get("metrics", [])))
    return out


def _fmt(v: float, kind: str) -> str:
    if kind == "pct":
        return f"{v:.1f}%"
    if kind == "sec":
        m, s = divmod(int(v), 60)
        return f"{m}:{s:02d}"
    if kind == "float":
        return f"{v:.2f}"
    return f"{int(v):,}".replace(",", " ")


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("-" * len(line))
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))


def _period(args) -> tuple[str, str]:
    return args.date_from, args.date_to


# ---------------------------------------------------------------------- commands
def cmd_counters(m: YandexMetrika, _a) -> None:
    rows = [[str(c["id"]), c["name"], c.get("site", ""), c.get("permission", ""), c.get("status", "")]
            for c in m.counters()]
    _print_table(["id", "название", "сайт", "доступ", "статус"], rows)


def cmd_goals(m: YandexMetrika, _a) -> None:
    rows = []
    for g in m.goals():
        cond = "; ".join(f"{c.get('type')}:{c.get('url', '')}" for c in g.get("conditions", []))
        rows.append([str(g["id"]), g["name"], g["type"], g.get("goal_source", ""), cond])
    _print_table(["id", "цель", "тип", "источник", "условие"], rows)


SUMMARY_METRICS = [
    ("ym:s:visits", "визиты", "int"),
    ("ym:s:users", "посетители", "int"),
    ("ym:s:pageviews", "просмотры", "int"),
    ("ym:s:bounceRate", "отказы", "pct"),
    ("ym:s:pageDepth", "глубина", "float"),
    ("ym:s:avgVisitDurationSeconds", "время на сайте", "sec"),
]


def cmd_summary(m: YandexMetrika, a) -> None:
    d1, d2 = _period(a)
    rep = m.data(",".join(k for k, _, _ in SUMMARY_METRICS), date1=d1, date2=d2)
    totals = rep.get("totals", [0] * len(SUMMARY_METRICS))
    print(f"Счётчик {m.counter_id}, период {d1} .. {d2}")
    for (_, title, kind), v in zip(SUMMARY_METRICS, totals):
        print(f"  {title:<16} {_fmt(v, kind)}")


def cmd_sources(m: YandexMetrika, a) -> None:
    d1, d2 = _period(a)
    rep = m.data("ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds",
                 "ym:s:lastTrafficSource", d1, d2)
    total = rep.get("totals", [0])[0] or 1
    rows = []
    for dims, met in _rows(rep):
        rows.append([dims[0], _fmt(met[0], "int"), f"{met[0] / total * 100:.1f}%",
                     _fmt(met[1], "int"), _fmt(met[2], "pct"), _fmt(met[3], "sec")])
    print(f"Каналы, {d1} .. {d2}, всего визитов {_fmt(total, 'int')}")
    _print_table(["канал", "визиты", "доля", "посетители", "отказы", "время"], rows)


def cmd_pages(m: YandexMetrika, a) -> None:
    d1, d2 = _period(a)
    rep = m.data("ym:s:visits,ym:s:bounceRate", "ym:s:startURLPath", d1, d2, limit=a.limit)
    rows = [[dims[0], _fmt(met[0], "int"), _fmt(met[1], "pct")] for dims, met in _rows(rep)]
    print(f"Страницы входа, {d1} .. {d2}")
    _print_table(["страница", "визиты", "отказы"], rows)


def cmd_goal(m: YandexMetrika, a) -> None:
    d1, d2 = _period(a)
    g = m.find_goal(a.goal)
    gid = g["id"]
    metrics = f"ym:s:goal{gid}reaches,ym:s:goal{gid}conversionRate,ym:s:visits"
    rep = m.data(metrics, "ym:s:lastTrafficSource", d1, d2)
    tot = rep.get("totals", [0, 0, 0])
    print(f"Цель «{g['name']}» (id {gid}), {d1} .. {d2}")
    print(f"  достижений {_fmt(tot[0], 'int')}, конверсия {_fmt(tot[1], 'pct')}, визитов {_fmt(tot[2], 'int')}")
    rows = [[dims[0], _fmt(met[0], "int"), _fmt(met[1], "pct"), _fmt(met[2], "int")]
            for dims, met in _rows(rep)]
    _print_table(["канал", "достижения", "конверсия", "визиты"], rows)


def cmd_goals_report(m: YandexMetrika, a) -> None:
    d1, d2 = _period(a)
    goals = m.goals()
    rows = []
    # Метрика принимает до 20 метрик за запрос: режем пачками по 10 целей (2 метрики на цель).
    for i in range(0, len(goals), 10):
        chunk = goals[i:i + 10]
        metrics = ",".join(f"ym:s:goal{g['id']}reaches,ym:s:goal{g['id']}conversionRate" for g in chunk)
        rep = m.data(metrics, date1=d1, date2=d2, sort="-ym:s:goal%dreaches" % chunk[0]["id"])
        tot = rep.get("totals", [])
        for j, g in enumerate(chunk):
            reaches, conv = tot[2 * j], tot[2 * j + 1]
            rows.append([str(g["id"]), g["name"], _fmt(reaches, "int"), _fmt(conv, "pct")])
    rows.sort(key=lambda r: -int(r[2].replace(" ", "") or 0))
    print(f"Цели, {d1} .. {d2}")
    _print_table(["id", "цель", "достижения", "конверсия"], rows)


def cmd_raw(m: YandexMetrika, a) -> None:
    d1, d2 = _period(a)
    rep = m.data(a.metrics, a.dimensions or "", d1, d2, a.filters or "", a.limit)
    print(json.dumps(rep, ensure_ascii=False, indent=2))


# -------------------------------------------------------------------------- main
def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--counter", default=None, help="id счётчика (по умолчанию из .env)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def with_period(sp):
        sp.add_argument("--from", dest="date_from", default="30daysAgo")
        sp.add_argument("--to", dest="date_to", default="yesterday")
        return sp

    sub.add_parser("counters")
    sub.add_parser("goals")
    with_period(sub.add_parser("summary"))
    with_period(sub.add_parser("sources"))
    sp = with_period(sub.add_parser("pages"))
    sp.add_argument("--limit", type=int, default=30)
    sp = with_period(sub.add_parser("goal"))
    sp.add_argument("goal", help="id цели или подстрока названия")
    with_period(sub.add_parser("goals-report"))
    sp = with_period(sub.add_parser("raw"))
    sp.add_argument("--metrics", required=True)
    sp.add_argument("--dimensions")
    sp.add_argument("--filters")
    sp.add_argument("--limit", type=int, default=50)

    a = p.parse_args(argv)
    env = read_env()
    token = env.get("YANDEX_METRIKA_ACCESS_TOKEN")
    if not token:
        raise SystemExit("В .env нет YANDEX_METRIKA_ACCESS_TOKEN")
    counter = a.counter or env.get("YANDEX_METRIKA_COUNTER_ID") or DEFAULT_COUNTER
    m = YandexMetrika(token, counter)

    {
        "counters": cmd_counters,
        "goals": cmd_goals,
        "summary": cmd_summary,
        "sources": cmd_sources,
        "pages": cmd_pages,
        "goal": cmd_goal,
        "goals-report": cmd_goals_report,
        "raw": cmd_raw,
    }[a.cmd](m, a)


if __name__ == "__main__":
    main(sys.argv[1:])

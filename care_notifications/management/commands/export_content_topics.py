"""Экспорт тем контента из базы знаний Службы заботы за календарный месяц.

Мост между БД календаря ухода (этот проект) и контент-системой codex-siberian.
Команда детерминированно выгружает ВСЕ работы, попадающие на указанный месяц,
со всей фактурой (тема, текст, препараты, видео, ссылка на страницу календаря).
Отбор до 12-15 тем и разметку под воронку делает уже скилл care-topics на той
стороне - здесь только полный, воспроизводимый снапшот-кандидат.

    python manage.py export_content_topics --month 2026-07
    python manage.py export_content_topics --month 2026-07 --out-dir /путь/к/references

Пишет два файла в out-dir:
    <month>.json  - машинный контракт для скилла
    <month>.md    - человекочитаемая версия (глазами проверить перед планом)

Парсер дат, тизер и URL берём из care_notifications - один источник правды с
дайджестом, чтобы темы в контенте и в рассылке не разъезжались.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from care_notifications.content import _make_summary, _plant_url
from care_notifications.date_parser import overlaps, parse_date_label

_MONTHS_NOM = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}

# Месяц -> сезон (совпадает с care_notifications/cards/seasons.py).
_MONTH_TO_SEASON = {
    1: "winter", 2: "winter", 3: "winter", 4: "spring", 5: "spring", 6: "summer",
    7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "winter", 12: "winter",
}
_SEASON_RU = {"spring": "Весна", "summer": "Лето", "autumn": "Осень", "winter": "Зима"}

# Полное тело работы для контентщика: длиннее тизера, но не весь лонгрид.
_BODY_MAX_CHARS = 700

# Снапшот коммитится в codex-siberian, где действует запрет на длинное тире.
# Нормализуем любое типографское тире в дефис ещё на выгрузке.
_DASHES = str.maketrans({"—": "-", "–": "-"})


def _dash(s: str) -> str:
    return (s or "").translate(_DASHES)


def _month_range(month_key: str) -> tuple[int, int, dt.date, dt.date]:
    """'2026-07' -> (year, month, первое_число, последнее_число)."""
    m = re.match(r"^(\d{4})-(\d{2})$", month_key or "")
    if not m:
        raise CommandError(f"Плохой --month={month_key!r}, нужен формат YYYY-MM (напр. 2026-07)")
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        raise CommandError(f"Месяц вне диапазона: {month}")
    first = dt.date(year, month, 1)
    last = dt.date(year, 12, 31) if month == 12 else dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    return year, month, first, last


def _clean_body(content_text: str, content_html: str) -> str:
    """Развёрнутое тело работы: plain-текст, без HTML, аккуратно обрезанное."""
    src = (content_text or "").strip()
    if not src and content_html:
        src = re.sub(r"<[^>]+>", " ", content_html)
    src = re.sub(r"[ \t]+", " ", src).strip()
    if len(src) <= _BODY_MAX_CHARS:
        return src
    return src[:_BODY_MAX_CHARS].rsplit(" ", 1)[0] + "…"


def _videos(videos_json) -> list[dict]:
    out = []
    for v in videos_json or []:
        if isinstance(v, dict) and v.get("url"):
            out.append({"label": (v.get("label") or "").strip(), "url": v["url"].strip()})
    return out


class Command(BaseCommand):
    help = "Выгрузить темы контента из календаря Службы заботы за месяц (JSON + Markdown)."

    def add_arguments(self, parser):
        parser.add_argument("--month", required=True, help="Месяц YYYY-MM, напр. 2026-07")
        parser.add_argument(
            "--out-dir",
            default=None,
            help="Куда положить <month>.json и <month>.md (по умолчанию BASE_DIR/exports/care-topics/)",
        )
        parser.add_argument("--site-url", default="https://gazony.ru", help="Базовый URL для ссылок")

    def handle(self, *args, **opts):
        from pages.models import CareCalendarPeriod, CareCalendarSeasonRecommendation

        month_key = opts["month"]
        year, month, first, last = _month_range(month_key)
        site_url = opts["site_url"].rstrip("/")
        season = _MONTH_TO_SEASON[month]
        window = (first, last)

        out_dir = Path(opts["out_dir"]) if opts["out_dir"] else Path(settings.BASE_DIR) / "exports" / "care-topics"
        out_dir.mkdir(parents=True, exist_ok=True)

        periods_qs = (
            CareCalendarPeriod.objects
            .select_related("plant", "plant__primary_category")
            .filter(plant__is_published=True)
            .order_by("plant__primary_category__sort_order", "plant__sort_order", "sort_order")
        )

        topics: list[dict] = []
        unparsed = 0
        for period in periods_qs:
            cat = period.plant.primary_category
            if cat is None:
                continue
            parsed = parse_date_label(period.date_label, year)
            if parsed is None:
                unparsed += 1
                continue
            if not overlaps(parsed, window):
                continue
            start, end = parsed
            topics.append({
                "category_slug": cat.slug,
                "category_label": _dash(cat.label),
                "plant_name": _dash(period.plant.name),
                "plant_latin": _dash(period.plant.latin or ""),
                "plant_slug": period.plant.slug,
                "date_label": _dash(period.date_label),
                "date_start": start.isoformat(),
                "date_end": end.isoformat(),
                "theme": _dash(_make_summary(period.theme, period.content_text, period.content_html)),
                "body": _dash(_clean_body(period.content_text, period.content_html)),
                "products": [_dash(str(p).strip()) for p in (period.products_json or []) if str(p).strip()],
                "videos": [{"label": _dash(v["label"]), "url": v["url"]} for v in _videos(period.videos_json)],
                "url": _plant_url(cat.slug, period.plant.slug, site_url),
            })

        topics.sort(key=lambda t: (t["date_start"], t["category_label"], t["plant_name"]))

        # Сезонные рекомендации для сезона месяца (общий контекст, не привязан к дате).
        season_recs = []
        recs_qs = (
            CareCalendarSeasonRecommendation.objects
            .select_related("plant", "plant__primary_category")
            .filter(season=season, plant__is_published=True)
            .order_by("plant__primary_category__sort_order", "sort_order")
        )
        for rec in recs_qs:
            body = (rec.body or "").strip()
            if not body:
                continue
            season_recs.append({
                "category_label": _dash(rec.plant.primary_category.label) if rec.plant.primary_category else "",
                "plant_name": _dash(rec.plant.name),
                "body": _dash(body),
            })

        payload = {
            "source": "care-service-calendar",
            "site": site_url,
            "month": month_key,
            "month_label": f"{_MONTHS_NOM[month]} {year}",
            "season": season,
            "season_label": _SEASON_RU[season],
            "topic_count": len(topics),
            "categories": sorted({t["category_label"] for t in topics}),
            "target_topics_per_month": "12-15",
            "topics": topics,
            "season_recommendations": season_recs,
        }

        json_path = out_dir / f"{month_key}.json"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        md_path = out_dir / f"{month_key}.md"
        md_path.write_text(self._render_markdown(payload), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(
            f"{payload['month_label']} ({payload['season_label']}): "
            f"{len(topics)} тем-кандидатов по {len(payload['categories'])} категориям, "
            f"{len(season_recs)} сезонных рекомендаций."
        ))
        if unparsed:
            self.stdout.write(f"Пропущено {unparsed} периодов с непарсимым date_label.")
        self.stdout.write(f"JSON: {json_path}")
        self.stdout.write(f"MD:   {md_path}")

    def _render_markdown(self, payload: dict) -> str:
        lines: list[str] = []
        lines.append(f"# Темы контента - Служба заботы, {payload['month_label']}")
        lines.append("")
        lines.append(
            f"Сезон: {payload['season_label']}. Кандидатов: {payload['topic_count']}. "
            f"Цель контент-плана: {payload['target_topics_per_month']} тем."
        )
        lines.append(f"Источник: {payload['source']} ({payload['site']}).")
        lines.append("")
        lines.append("Это сырьё для скилла care-topics: полный список работ месяца. "
                     "Отбор и разметку под воронку делает скилл, не человек вручную.")
        lines.append("")

        by_cat: dict[str, list[dict]] = {}
        for t in payload["topics"]:
            by_cat.setdefault(t["category_label"], []).append(t)

        for cat_label in payload["categories"]:
            items = by_cat.get(cat_label, [])
            lines.append(f"## {cat_label} ({len(items)})")
            lines.append("")
            for t in items:
                title = t["theme"] or t["plant_name"]
                lines.append(f"### {t['plant_name']} - {t['date_label']}")
                lines.append("")
                lines.append(f"Тема: {title}")
                lines.append("")
                if t["body"]:
                    lines.append(t["body"])
                    lines.append("")
                if t["products"]:
                    lines.append(f"Препараты: {', '.join(t['products'])}")
                if t["videos"]:
                    vids = ", ".join(v["url"] for v in t["videos"])
                    lines.append(f"Видео: {vids}")
                lines.append(f"Ссылка: {t['url']}")
                lines.append("")

        if payload["season_recommendations"]:
            lines.append(f"## Сезонные рекомендации ({payload['season_label']})")
            lines.append("")
            for rec in payload["season_recommendations"]:
                head = f"{rec['plant_name']}"
                if rec["category_label"]:
                    head += f" ({rec['category_label']})"
                lines.append(f"- {head}: {rec['body']}")
            lines.append("")

        return "\n".join(lines)

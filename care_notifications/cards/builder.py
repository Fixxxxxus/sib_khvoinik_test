"""Сборка карточек недели: контент категорий + промо, запись PNG и манифеста."""
from __future__ import annotations

import errno
import json
import os
import pathlib
import time

from django.conf import settings

from care_notifications.date_parser import iso_week_range, overlaps, parse_date_label

from .palettes import CATEGORY_ICON, CATEGORY_LABEL_FALLBACK
from .renderer import render_html_to_png
from .seasons import season_for_date
from .shaper import build_category_card
from .templates_html import render_card_html, render_promo_html

HEADLINE_FALLBACK = "Что важно на этой неделе"
SUBSCRIBABLE_SLUGS = ["derevya", "kustarniki", "mnogoletniki", "rozy", "gazon"]


def week_dir(week_key: str) -> pathlib.Path:
    return pathlib.Path(settings.MEDIA_ROOT) / "care_cards" / week_key


def manifest_path(week_key: str) -> pathlib.Path:
    return week_dir(week_key) / "manifest.json"


def _periods_for(cat_slug: str, rng) -> list[tuple[str, str]]:
    from pages.models import CareCalendarPeriod
    qs = (CareCalendarPeriod.objects
          .select_related("plant", "plant__primary_category")
          .filter(plant__primary_category__slug=cat_slug, plant__is_published=True)
          .order_by("plant__sort_order", "sort_order"))
    out = []
    for p in qs:
        parsed = parse_date_label(p.date_label, rng[0].year)
        if parsed and overlaps(parsed, rng):
            out.append((p.content_text or "", p.theme or ""))
    return out


def _labels() -> dict[str, str]:
    from pages.models import CareCalendarCategory
    return {c.slug: c.label for c in CareCalendarCategory.objects.all()}


def build_week_cards(week_key: str, *, force: bool = False) -> dict:
    mpath = manifest_path(week_key)
    if mpath.exists() and not force:
        return json.loads(mpath.read_text(encoding="utf-8"))

    rng = iso_week_range(week_key)
    if rng is None:
        raise ValueError(f"bad week_key: {week_key}")
    season = season_for_date(rng[0])
    labels = _labels()
    wdir = week_dir(week_key)

    jobs: list[tuple[str, pathlib.Path]] = []
    categories: dict[str, dict] = {}
    for slug in SUBSCRIBABLE_SLUGS:
        periods = _periods_for(slug, rng)
        if not periods:
            continue
        card = build_category_card(periods, fallback_headline=HEADLINE_FALLBACK)
        if not card["bullets"]:
            continue
        label = labels.get(slug) or CATEGORY_LABEL_FALLBACK.get(slug, slug)
        html_doc = render_card_html(
            season=season, category_label=label,
            category_icon=CATEGORY_ICON.get(slug, "leaf"),
            headline=card["headline"], bullets=card["bullets"])
        fname = f"{slug}.png"
        jobs.append((html_doc, wdir / fname))
        categories[slug] = {"label": label, "file": fname}

    promo = None
    if categories:  # промо добавляем только когда есть контентный альбом
        promo_file = f"promo_{season}.png"
        jobs.append((render_promo_html(season), wdir / promo_file))
        promo = {"file": promo_file}

    render_html_to_png(jobs)

    manifest = {"week_key": week_key, "season": season,
                "categories": categories, "promo": promo}
    wdir.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest


def ensure_week_cards(week_key: str) -> dict:
    """Идемпотентно гарантировать карточки недели (с файл-локом против гонки)."""
    mpath = manifest_path(week_key)
    if mpath.exists():
        return json.loads(mpath.read_text(encoding="utf-8"))
    lock = week_dir(week_key).with_suffix(".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
        for _ in range(60):  # ждём чужой рендер до 60 с
            time.sleep(1)
            if mpath.exists():
                return json.loads(mpath.read_text(encoding="utf-8"))
        return build_week_cards(week_key)  # лок завис - рисуем сами
    try:
        return build_week_cards(week_key)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _abs(site_url: str, week_key: str, fname: str) -> str:
    media = settings.MEDIA_URL.rstrip("/")
    return f"{site_url.rstrip('/')}{media}/care_cards/{week_key}/{fname}"


def category_image_url(week_key: str, category_slug: str, *, site_url: str) -> str | None:
    mpath = manifest_path(week_key)
    if not mpath.exists():
        return None
    man = json.loads(mpath.read_text(encoding="utf-8"))
    cat = man.get("categories", {}).get(category_slug)
    return _abs(site_url, week_key, cat["file"]) if cat else None


def promo_image_url(week_key: str, *, site_url: str) -> str | None:
    mpath = manifest_path(week_key)
    if not mpath.exists():
        return None
    man = json.loads(mpath.read_text(encoding="utf-8"))
    promo = man.get("promo")
    return _abs(site_url, week_key, promo["file"]) if promo else None

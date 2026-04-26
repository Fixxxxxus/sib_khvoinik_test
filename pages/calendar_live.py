"""Контекст календаря ухода: БД (USE_DATABASE_CALENDAR) или статика из data/calendar_data."""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings
from django.db.models import Prefetch, Q

from pages.calendar_data import CALENDAR_PERIODS
from pages.models import (
    CareCalendarCategory,
    CareCalendarPeriod,
    CareCalendarPlant,
    CareCalendarPlantGalleryImage,
    CareCalendarSeasonRecommendation,
)


def _period_labels_ordered(labels: set[str]) -> list[str]:
    """Сохраняем привычный порядок из статического списка, новые подписи — в конце по алфавиту."""
    order_map = {l: i for i, l in enumerate(CALENDAR_PERIODS)}
    rest = sorted(x for x in labels if x not in order_map)
    ordered = [x for x in CALENDAR_PERIODS if x in labels]
    return ordered + rest


def _varieties_display(raw: Any) -> str:
    if isinstance(raw, list):
        parts = [str(x).strip() for x in raw if str(x).strip()]
        return ", ".join(parts)
    return ""


_PERIOD_IMAGE_FIELDS = tuple(f"period_image_{i}" for i in range(1, 7))


def _period_uploaded_image_urls(per: CareCalendarPeriod) -> list[str]:
    urls: list[str] = []
    for name in _PERIOD_IMAGE_FIELDS:
        f = getattr(per, name, None)
        if not f:
            continue
        try:
            urls.append(f.url)
        except ValueError:
            continue
    return urls


_MD_LINK_RE = re.compile(r"^\[(?P<text>.+?)\]\((?P<href>[^)]*)\)$", re.DOTALL)


def _strip_md_link(label: str, url: str) -> tuple[str, str]:
    """Артефакт выгрузки из Yonote: label вида `[Текст](href)`. Раскладываем в чистый текст и URL."""
    m = _MD_LINK_RE.match(label.strip())
    if not m:
        return label.strip(), url
    text = m.group("text").strip()
    href = m.group("href").strip()
    return text, url or href


def _videos_as_list(raw: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            url = str(item.get("url") or "").strip()
            label, url = _strip_md_link(label, url)
            if label or url:
                out.append({"label": label or url, "url": url})
        elif isinstance(item, str) and item.strip():
            label, url = _strip_md_link(item.strip(), "")
            if label or url:
                out.append({"label": label or url, "url": url})
    return out


def _plant_to_dict(
    plant: CareCalendarPlant,
    *,
    gallery_urls: list[str] | None = None,
) -> dict[str, Any]:
    v_raw = plant.varieties_json or []
    periods_out: list[dict[str, Any]] = []
    for per in plant.periods.all():
        uploaded = _period_uploaded_image_urls(per)
        json_imgs = list(per.images_json or []) if isinstance(per.images_json, list) else []
        imgs = uploaded + json_imgs
        products = per.products_json if isinstance(per.products_json, list) else []
        videos = _videos_as_list(per.videos_json)
        periods_out.append(
            {
                "date_label": per.date_label,
                "theme": per.theme or "",
                "content_text": per.content_text or "",
                "content_html": per.content_html or "",
                "images": imgs,
                "products": products,
                "videos": videos,
            }
        )

    cat_slugs: list[str] = []
    for c in plant.categories.all():
        if c.slug not in cat_slugs:
            cat_slugs.append(c.slug)
    primary_slug = plant.primary_category.slug
    if primary_slug not in cat_slugs:
        cat_slugs.insert(0, primary_slug)

    season_rows: list[dict[str, Any]] = []
    for rec in plant.season_recommendations.all():
        season_rows.append(
            {
                "season": rec.season,
                "season_label": rec.get_season_display(),
                "body": rec.body,
                "sort_order": rec.sort_order,
            }
        )

    return {
        "slug": plant.slug,
        "name": plant.name,
        "latin": (plant.latin or "").strip(),
        "varieties": _varieties_display(v_raw),
        "category_slug": primary_slug,
        "category_slugs_all": cat_slugs,
        "yonote_id": (plant.yonote_id or "").strip(),
        "description": (plant.description or "").strip(),
        "periods": periods_out,
        "season_recommendations": season_rows,
        "gallery_image_urls": gallery_urls or [],
        "show_paid_service_cta": plant.show_paid_service_cta,
    }


def get_calendar_page_from_database() -> dict[str, Any] | None:
    if not getattr(settings, "USE_DATABASE_CALENDAR", False):
        return None

    plants_qs = (
        CareCalendarPlant.objects.filter(is_published=True)
        .select_related("primary_category")
        .prefetch_related(
            "categories",
            Prefetch(
                "periods",
                queryset=CareCalendarPeriod.objects.order_by("sort_order", "pk"),
            ),
            Prefetch(
                "gallery_images",
                queryset=CareCalendarPlantGalleryImage.objects.order_by("sort_order", "pk"),
            ),
            Prefetch(
                "season_recommendations",
                queryset=CareCalendarSeasonRecommendation.objects.order_by("season", "sort_order", "pk"),
            ),
        )
        .order_by("primary_category__sort_order", "sort_order", "name")
    )
    if not plants_qs.exists():
        return None

    plants_list: list[dict[str, Any]] = []
    all_labels: set[str] = set()
    for p in plants_qs:
        g_urls = []
        for gi in p.gallery_images.all():
            try:
                if gi.image:
                    g_urls.append(gi.image.url)
            except ValueError:
                pass
        d = _plant_to_dict(p, gallery_urls=g_urls)
        plants_list.append(d)
        for per in d["periods"]:
            if per.get("date_label"):
                all_labels.add(per["date_label"])

    categories_out: list[dict[str, Any]] = []
    for c in CareCalendarCategory.objects.order_by("sort_order", "label"):
        n = (
            CareCalendarPlant.objects.filter(is_published=True)
            .filter(Q(primary_category=c) | Q(categories=c))
            .distinct()
            .count()
        )
        categories_out.append({"slug": c.slug, "label": c.label, "count": n})

    return {
        "categories": categories_out,
        "periods": _period_labels_ordered(all_labels) if all_labels else list(CALENDAR_PERIODS),
        "plants": plants_list,
    }


def _normalize_static_plants(plants: Any) -> list[Any]:
    """Чистит видео-label у статических растений: `[Текст](href)` → `Текст`."""
    if not isinstance(plants, list):
        return plants
    out: list[Any] = []
    for plant in plants:
        if not isinstance(plant, dict):
            out.append(plant)
            continue
        new_periods: list[Any] = []
        for per in plant.get("periods") or []:
            if isinstance(per, dict) and isinstance(per.get("videos"), list):
                per = {**per, "videos": _videos_as_list(per["videos"])}
            new_periods.append(per)
        out.append({**plant, "periods": new_periods})
    return out


def merge_calendar_base(base: dict[str, Any]) -> dict[str, Any]:
    """Подменяет categories / periods / plants из БД, если включён флаг и есть данные."""
    live = get_calendar_page_from_database()
    if not live:
        out = dict(base)
        out["plants"] = _normalize_static_plants(out.get("plants"))
        return out
    out = dict(base)
    out.update(live)
    return out

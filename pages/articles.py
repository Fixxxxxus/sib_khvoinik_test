"""
Статьи /stati/: мерж статей из БД (загружены через API контент-фабрики) со
старыми статьями-диктами из pages/data.py.

Единый формат - дикт с ключами slug, title, excerpt, lead, sections, faq,
date_published, date_modified, image / image_url, image_alt. Шаблоны и
pages/seo.py работают только с этим диктом и не знают, откуда он пришёл.

Видимость: published - всегда; scheduled - с даты публикации (Asia/Krasnoyarsk);
draft - только по preview-ссылке /stati/<slug>/?preview=<токен>.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

from django.conf import settings
from django.utils import timezone

from .data import STATI_PAGE

# Ключи, которые контент-фабрика может задавать в теле статьи.
ARTICLE_TEXT_FIELDS = (
    "title",
    "excerpt",
    "lead",
    "seo_title",
    "meta_description",
    "image_path",
    "image_alt",
)


def preview_token(slug: str) -> str:
    """Постоянный токен предпросмотра черновика: HMAC(slug) на SECRET_KEY."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"article-preview:{slug}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def preview_path(slug: str) -> str:
    return f"/stati/{slug}/?preview={preview_token(slug)}"


def article_to_dict(obj) -> dict[str, Any]:
    """Модель Article -> дикт в формате STATI_PAGE['articles']."""
    data: dict[str, Any] = {
        "slug": obj.slug,
        "title": obj.title,
        "excerpt": obj.excerpt,
        "lead": obj.lead,
        "sections": obj.sections or [],
        "faq": obj.faq or [],
        "seo_title": obj.seo_title or obj.title,
        "meta_description": obj.meta_description or obj.excerpt,
        "date_published": obj.date_published.isoformat() if obj.date_published else "",
        "date_modified": (
            obj.date_modified.isoformat()
            if obj.date_modified
            else (obj.date_published.isoformat() if obj.date_published else "")
        ),
        "image_alt": obj.image_alt,
        "status": obj.status,
        "from_db": True,
    }
    # Обложка: загруженный файл (MEDIA, готовый URL) важнее пути в static.
    uploaded = obj.image_url
    if uploaded:
        data["image_url"] = uploaded
        data["image"] = ""
    else:
        data["image"] = obj.image_path or ""
        data["image_url"] = ""
    return data


def _static_articles() -> list[dict[str, Any]]:
    return list(STATI_PAGE.get("articles") or [])


def db_articles(include_hidden: bool = False) -> list[dict[str, Any]]:
    """Статьи из БД: видимые публично, либо все (для админки/preview)."""
    from .models import Article

    today = timezone.localdate()
    items = []
    for obj in Article.objects.all():
        if include_hidden or obj.is_visible(today):
            items.append(article_to_dict(obj))
    return items


def merged_articles() -> list[dict[str, Any]]:
    """Публичный список: свежие статьи из БД сверху, затем статика из data.py."""
    from_db = db_articles()
    from_db.sort(key=lambda a: (a.get("date_published") or "", a["slug"]), reverse=True)
    seen = {a["slug"] for a in from_db}
    return from_db + [a for a in _static_articles() if a.get("slug") not in seen]


def find_article(slug: str, preview: str = "") -> tuple[dict[str, Any] | None, bool]:
    """
    Ищет статью по слагу. Возвращает (дикт, is_preview).

    Скрытая статья (черновик или ещё не наступила дата) отдаётся только при
    верном токене предпросмотра; такая страница помечается noindex.
    """
    from .models import Article

    obj = Article.objects.filter(slug=slug).first()
    if obj is not None:
        if obj.is_visible():
            return article_to_dict(obj), False
        if preview and hmac.compare_digest(preview, preview_token(slug)):
            return article_to_dict(obj), True
        return None, False
    for art in _static_articles():
        if art.get("slug") == slug:
            return art, False
    return None, False

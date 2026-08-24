"""
API публикации статей из контент-фабрики (проект siberian-cursor) на gazony.ru.

Маркетолог работает в Cursor, доступа к серверу и коду у него нет: скилл
`publish-article` шлёт сюда готовую статью JSON-ом, статья садится в БД
черновиком или планом на дату, картинка догружается отдельным запросом.

Авторизация - общий секрет в заголовке `X-Api-Token`, значение берётся из
переменной окружения ARTICLE_API_TOKEN. Без токена эндпоинты выключены.

    POST   /api/articles/               upsert статьи по slug (JSON)
    POST   /api/articles/<slug>/image/  загрузка обложки (multipart, поле image)
    GET    /api/articles/               список статей из БД со статусами и ссылками
"""
from __future__ import annotations

import hmac
import json
import logging
import re
from datetime import date
from typing import Any

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .articles import preview_path
from .models import Article

logger = logging.getLogger(__name__)

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}

STATUSES = {Article.STATUS_DRAFT, Article.STATUS_SCHEDULED, Article.STATUS_PUBLISHED}


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _check_token(request: HttpRequest) -> None:
    expected = (getattr(settings, "ARTICLE_API_TOKEN", "") or "").strip()
    if not expected:
        raise ApiError("Публикация статей через API выключена: не задан ARTICLE_API_TOKEN.", 503)
    got = (request.headers.get("X-Api-Token") or "").strip()
    if not got or not hmac.compare_digest(got, expected):
        raise ApiError("Неверный или отсутствующий X-Api-Token.", 401)


def _clean_dashes(value: str, field: str, warnings: list[str]) -> str:
    """Длинное тире в проекте запрещено: молча меняем на дефис и предупреждаем."""
    if "—" in value:
        warnings.append(f"В поле «{field}» было длинное тире, заменено на дефис.")
        value = value.replace("—", "-")
    return value


def _text(payload: dict, key: str, warnings: list[str], required: bool = False, limit: int = 0) -> str:
    raw = payload.get(key)
    if raw is None:
        raw = ""
    if not isinstance(raw, str):
        raise ApiError(f"Поле «{key}» должно быть строкой.")
    value = _clean_dashes(raw.strip(), key, warnings)
    if required and not value:
        raise ApiError(f"Поле «{key}» обязательно.")
    if limit and len(value) > limit:
        raise ApiError(f"Поле «{key}» длиннее {limit} символов.")
    return value


def _str_list(raw: Any, field: str, warnings: list[str]) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApiError(f"Поле «{field}» должно быть списком строк.")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, str):
            raise ApiError(f"«{field}[{i}]» должно быть строкой.")
        text = _clean_dashes(item.strip(), field, warnings)
        if text:
            out.append(text)
    return out


def _parse_sections(raw: Any, warnings: list[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ApiError("Поле «sections» обязательно: непустой список разделов статьи.")
    sections: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ApiError(f"«sections[{i}]» должен быть объектом.")
        heading = item.get("heading")
        if not isinstance(heading, str) or not heading.strip():
            raise ApiError(f"«sections[{i}].heading» обязателен.")
        section: dict[str, Any] = {
            "heading": _clean_dashes(heading.strip(), f"sections[{i}].heading", warnings)
        }
        paragraphs = _str_list(item.get("paragraphs"), f"sections[{i}].paragraphs", warnings)
        if not paragraphs:
            raise ApiError(f"«sections[{i}].paragraphs» обязателен: хотя бы один абзац.")
        section["paragraphs"] = paragraphs
        for key in ("steps", "list"):
            values = _str_list(item.get(key), f"sections[{i}].{key}", warnings)
            if values:
                section[key] = values
        table = item.get("table")
        if table:
            if not isinstance(table, dict):
                raise ApiError(f"«sections[{i}].table» должен быть объектом.")
            headers = _str_list(table.get("headers"), f"sections[{i}].table.headers", warnings)
            rows_raw = table.get("rows")
            if not headers or not isinstance(rows_raw, list) or not rows_raw:
                raise ApiError(f"«sections[{i}].table» требует headers[] и rows[][].")
            rows = []
            for j, row in enumerate(rows_raw):
                cells = _str_list(row, f"sections[{i}].table.rows[{j}]", warnings)
                if len(cells) != len(headers):
                    raise ApiError(
                        f"«sections[{i}].table.rows[{j}]»: {len(cells)} ячеек при {len(headers)} колонках."
                    )
                rows.append(cells)
            section["table"] = {"headers": headers, "rows": rows}
        sections.append(section)
    return sections


def _parse_faq(raw: Any, warnings: list[str]) -> list[dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApiError("Поле «faq» должно быть списком объектов {q, a}.")
    faq = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ApiError(f"«faq[{i}]» должен быть объектом {{q, a}}.")
        q = item.get("q")
        a = item.get("a")
        if not isinstance(q, str) or not q.strip() or not isinstance(a, str) or not a.strip():
            raise ApiError(f"«faq[{i}]» требует непустые q и a.")
        faq.append(
            {
                "q": _clean_dashes(q.strip(), f"faq[{i}].q", warnings),
                "a": _clean_dashes(a.strip(), f"faq[{i}].a", warnings),
            }
        )
    return faq


def _parse_date(raw: Any, field: str, required: bool = False) -> date | None:
    if raw in (None, ""):
        if required:
            raise ApiError(f"Поле «{field}» обязательно в формате ГГГГ-ММ-ДД.")
        return None
    if not isinstance(raw, str):
        raise ApiError(f"Поле «{field}» должно быть строкой ГГГГ-ММ-ДД.")
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        raise ApiError(f"Поле «{field}»: ожидается дата ГГГГ-ММ-ДД, получено «{raw}».")


def _article_payload(request: HttpRequest, obj: Article) -> dict[str, Any]:
    origin = f"{request.scheme}://{request.get_host()}"
    return {
        "slug": obj.slug,
        "title": obj.title,
        "status": obj.status,
        "date_published": obj.date_published.isoformat() if obj.date_published else "",
        "visible": obj.is_visible(),
        "url": f"{origin}/stati/{obj.slug}/",
        "preview_url": f"{origin}{preview_path(obj.slug)}",
        "has_image": bool(obj.image_upload or obj.image_path),
        "image_url": obj.image_url or obj.image_path,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else "",
    }


@csrf_exempt
@require_POST
def articles_upsert(request: HttpRequest) -> JsonResponse:
    """Создаёт или обновляет статью по slug. Тело - JSON, см. docstring модуля."""
    try:
        _check_token(request)
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError("Тело запроса должно быть валидным JSON в UTF-8.")
        if not isinstance(payload, dict):
            raise ApiError("Тело запроса должно быть объектом JSON.")

        warnings: list[str] = []
        slug = _text(payload, "slug", warnings, required=True, limit=200)
        if not SLUG_RE.match(slug):
            raise ApiError("Поле «slug»: только строчная латиница, цифры и дефисы.")

        status = (payload.get("status") or Article.STATUS_DRAFT).strip()
        if status not in STATUSES:
            raise ApiError(f"Поле «status»: одно из {sorted(STATUSES)}.")

        fields = {
            "title": _text(payload, "title", warnings, required=True, limit=300),
            "excerpt": _text(payload, "excerpt", warnings, required=True, limit=1000),
            "lead": _text(payload, "lead", warnings),
            "seo_title": _text(payload, "seo_title", warnings, limit=300),
            "meta_description": _text(payload, "meta_description", warnings, limit=500),
            "image_path": _text(payload, "image_path", warnings, limit=300).lstrip("/"),
            "image_alt": _text(payload, "image_alt", warnings, limit=300),
            "sections": _parse_sections(payload.get("sections"), warnings),
            "faq": _parse_faq(payload.get("faq"), warnings),
            "status": status,
            "date_published": _parse_date(payload.get("date_published"), "date_published", required=True),
            "date_modified": _parse_date(payload.get("date_modified"), "date_modified"),
            "source": _text(payload, "source", warnings, limit=100) or "api",
        }
        if fields["image_path"].startswith("static/"):
            fields["image_path"] = fields["image_path"][len("static/") :]

        obj = Article.objects.filter(slug=slug).first()
        created = obj is None
        if created:
            obj = Article(slug=slug)
        else:
            # Обложку, загруженную файлом, повторный upsert текста не сбрасывает.
            if obj.image_upload and not fields["image_path"]:
                fields.pop("image_path")
        for key, value in fields.items():
            setattr(obj, key, value)
        obj.full_clean(exclude=["image_upload"])
        obj.save()

        return JsonResponse(
            {
                "ok": True,
                "created": created,
                "warnings": warnings,
                "article": _article_payload(request, obj),
            },
            json_dumps_params={"ensure_ascii": False},
        )
    except ApiError as exc:
        return JsonResponse(
            {"ok": False, "error": exc.message},
            status=exc.status,
            json_dumps_params={"ensure_ascii": False},
        )
    except Exception:
        logger.exception("articles_upsert failed")
        return JsonResponse({"ok": False, "error": "Внутренняя ошибка сервера."}, status=500)


@csrf_exempt
@require_POST
def articles_image(request: HttpRequest, slug: str) -> JsonResponse:
    """Грузит обложку статьи: multipart/form-data, поле image (jpg/png/webp, до 8 МБ)."""
    try:
        _check_token(request)
        obj = Article.objects.filter(slug=slug).first()
        if obj is None:
            raise ApiError(f"Статья «{slug}» не найдена, сначала загрузите текст.", 404)
        upload = request.FILES.get("image")
        if upload is None:
            raise ApiError("Не передан файл в поле «image».")
        if upload.size > MAX_IMAGE_BYTES:
            raise ApiError(f"Файл больше {MAX_IMAGE_BYTES // (1024 * 1024)} МБ.")
        name = (upload.name or "").lower()
        ext = name[name.rfind(".") :] if "." in name else ""
        if ext not in ALLOWED_IMAGE_EXT:
            raise ApiError(f"Разрешены форматы: {', '.join(sorted(ALLOWED_IMAGE_EXT))}.")

        obj.image_upload.save(f"{slug}{ext}", upload, save=False)
        alt = (request.POST.get("image_alt") or "").strip().replace("—", "-")
        if alt:
            obj.image_alt = alt[:300]
        obj.save()
        return JsonResponse(
            {"ok": True, "article": _article_payload(request, obj)},
            json_dumps_params={"ensure_ascii": False},
        )
    except ApiError as exc:
        return JsonResponse(
            {"ok": False, "error": exc.message},
            status=exc.status,
            json_dumps_params={"ensure_ascii": False},
        )
    except Exception:
        logger.exception("articles_image failed")
        return JsonResponse({"ok": False, "error": "Внутренняя ошибка сервера."}, status=500)


@require_GET
def articles_list(request: HttpRequest) -> JsonResponse:
    """Список статей из БД со статусами: чтобы скилл видел, что уже загружено."""
    try:
        _check_token(request)
    except ApiError as exc:
        return JsonResponse(
            {"ok": False, "error": exc.message},
            status=exc.status,
            json_dumps_params={"ensure_ascii": False},
        )
    items = [_article_payload(request, obj) for obj in Article.objects.all()]
    return JsonResponse(
        {"ok": True, "count": len(items), "articles": items},
        json_dumps_params={"ensure_ascii": False},
    )

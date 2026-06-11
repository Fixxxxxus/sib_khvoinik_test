"""TTL-кэш собранного каталога (merged-растения, категории) на процесс.

Зачем: сборка каталога (запросы к БД + merge + display-поля) выполнялась на каждый
HTTP-запрос и давала TTFB 1.5-2.2s на проде. Кэшируем готовый результат в памяти.

Инвалидация двухуровневая:
- сигналы post_save/post_delete моделей каталога сбрасывают кэш в текущем процессе
  (актуально для админки: правка сразу видна в том же воркере);
- TTL (settings.CATALOG_CACHE_TTL, секунды) страхует остальные gunicorn-воркеры,
  до которых сигнал из процесса админки не долетает.

ВАЖНО: закэшированные dict растений нигде в request-пути не мутируются
(views/catalog_nav/catalog_products/templatetags только читают), поэтому из кэша
отдаются неглубокие копии списков (сами dict не копируются).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from django.conf import settings

_lock = threading.Lock()
# ключ -> (момент истечения по time.monotonic, значение)
_store: dict[str, tuple[float, Any]] = {}


def _ttl_seconds() -> float:
    try:
        return float(getattr(settings, "CATALOG_CACHE_TTL", 120))
    except (TypeError, ValueError):
        return 120.0


def get_or_build(key: str, builder: Callable[[], Any]) -> Any:
    """Вернуть значение из кэша или собрать через builder и закэшировать.

    При TTL <= 0 кэш отключён: всегда зовём builder (удобно для отладки).
    Сборка идёт вне лока, чтобы не блокировать другие потоки на время запросов к БД.
    """
    ttl = _ttl_seconds()
    if ttl <= 0:
        return builder()
    now = time.monotonic()
    with _lock:
        item = _store.get(key)
        if item is not None and item[0] > now:
            return item[1]
    value = builder()
    with _lock:
        _store[key] = (time.monotonic() + ttl, value)
    return value


def invalidate(*args: Any, **kwargs: Any) -> None:
    """Сбросить весь кэш каталога. Сигнатура совместима с Django-сигналами."""
    with _lock:
        _store.clear()


def register_invalidation_signals() -> None:
    """Подписать post_save/post_delete моделей каталога на сброс кэша.

    Вызывается из PagesConfig.ready(). Используем apps.get_model, чтобы
    не импортировать models на этапе загрузки приложений.
    """
    from django.apps import apps
    from django.db.models.signals import post_delete, post_save

    model_names = (
        "CatalogCategory",
        "CatalogSubcategory",
        "Plant",
        "PlantVariant",
        "PlantGalleryImage",
        "PlantCharacteristic",
    )
    for name in model_names:
        model = apps.get_model("pages", name)
        post_save.connect(invalidate, sender=model, dispatch_uid=f"catalog_cache_save_{name}")
        post_delete.connect(invalidate, sender=model, dispatch_uid=f"catalog_cache_delete_{name}")

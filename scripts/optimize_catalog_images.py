#!/usr/bin/env python3
"""Оптимизация изображений каталога: генерация webp-версий рядом с исходниками.

Для каждого .png/.jpg/.jpeg в static/media/images/catalog/ (рекурсивно) создаёт:
  - <stem>.webp       : максимальная сторона 1200px, quality 80;
  - <stem>.thumb.webp : максимальная сторона 480px, quality 75.

Исходники не удаляются. Повторный запуск пропускает уже актуальные webp
(существует и новее исходника); ключ --force пересобирает всё.

Ключ --sync-docs копирует сгенерированные .webp в зеркало
docs/static/media/images/catalog/ с сохранением структуры.

Запуск из корня проекта:
    python3 scripts/optimize_catalog_images.py [--force] [--sync-docs]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageOps

BASE_DIR = Path(__file__).resolve().parent.parent
CATALOG_DIR = BASE_DIR / "static" / "media" / "images" / "catalog"
DOCS_CATALOG_DIR = BASE_DIR / "docs" / "static" / "media" / "images" / "catalog"

SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg"}

# Параметры основной версии и миниатюры: (макс. сторона, quality)
MAIN_PARAMS = (1200, 80)
THUMB_PARAMS = (480, 75)


def is_up_to_date(src: Path, dst: Path) -> bool:
    """webp существует и не старше исходника: пересборка не нужна."""
    return dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime


def convert(img: Image.Image, dst: Path, max_side: int, quality: int) -> None:
    """Сохраняет копию img в webp, ужимая длинную сторону до max_side (без апскейла)."""
    out = img.copy()
    width, height = out.size
    longest = max(width, height)
    if longest > max_side:
        scale = max_side / longest
        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        out = out.resize(new_size, Image.Resampling.LANCZOS)
    # Альфа-канал сохраняем (webp его поддерживает), палитру разворачиваем
    if out.mode == "P":
        out = out.convert("RGBA" if "transparency" in out.info else "RGB")
    elif out.mode not in ("RGB", "RGBA"):
        out = out.convert("RGBA" if "A" in out.getbands() else "RGB")
    out.save(dst, format="WEBP", quality=quality, method=6)


def process_file(src: Path, force: bool) -> tuple[list[Path], bool]:
    """Создаёт webp-пару для исходника. Возвращает (созданные файлы, был ли пропуск)."""
    main_dst = src.with_suffix(".webp")
    thumb_dst = src.with_name(src.stem + ".thumb.webp")

    targets = []
    if force or not is_up_to_date(src, main_dst):
        targets.append((main_dst, MAIN_PARAMS))
    if force or not is_up_to_date(src, thumb_dst):
        targets.append((thumb_dst, THUMB_PARAMS))
    if not targets:
        return [], True

    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)
        created = []
        for dst, (max_side, quality) in targets:
            convert(img, dst, max_side, quality)
            created.append(dst)
    return created, False


def sync_docs(webp_files: list[Path]) -> int:
    """Копирует webp в зеркало docs/ с сохранением относительной структуры."""
    copied = 0
    for path in webp_files:
        rel = path.relative_to(CATALOG_DIR)
        dst = DOCS_CATALOG_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)
        copied += 1
    return copied


def human(size: int) -> str:
    """Размер в человекочитаемом виде."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Генерация webp для изображений каталога")
    parser.add_argument("--force", action="store_true", help="пересобрать все webp заново")
    parser.add_argument(
        "--sync-docs", action="store_true",
        help="скопировать все webp в docs/static/media/images/catalog/",
    )
    args = parser.parse_args()

    if not CATALOG_DIR.is_dir():
        print(f"Не найдена директория {CATALOG_DIR}", file=sys.stderr)
        return 1

    sources = sorted(
        p for p in CATALOG_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES
    )

    processed = 0
    skipped = 0
    errors = 0
    for src in sources:
        try:
            created, was_skipped = process_file(src, args.force)
        except Exception as exc:  # noqa: BLE001 - один битый файл не должен ронять прогон
            errors += 1
            print(f"ОШИБКА {src.relative_to(BASE_DIR)}: {exc}", file=sys.stderr)
            continue
        if was_skipped:
            skipped += 1
        else:
            processed += 1

    all_webp = sorted(p for p in CATALOG_DIR.rglob("*.webp") if p.is_file())

    src_total = sum(p.stat().st_size for p in sources)
    webp_total = sum(p.stat().st_size for p in all_webp)

    print(f"Исходников найдено:  {len(sources)}")
    print(f"Обработано:          {processed}")
    print(f"Пропущено (актуально): {skipped}")
    if errors:
        print(f"Ошибок:              {errors}")
    print(f"Размер исходников:   {human(src_total)}")
    print(f"Размер webp ({len(all_webp)} шт.): {human(webp_total)}")

    if args.sync_docs:
        copied = sync_docs(all_webp)
        print(f"Скопировано в docs/: {copied}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

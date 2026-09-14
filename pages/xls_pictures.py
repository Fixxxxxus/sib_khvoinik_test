"""Картинки из прайса 1С в формате xls (BIFF8) по строкам листа.

xlrd картинки не читает, LibreOffice на сервере нет, поэтому разбираем файл
сами. Устройство ровно такое, какое нужно, чтобы вытащить картинку строки:

- OLE-контейнер, поток «Workbook», внутри записи BIFF: тип (2 байта),
  длина (2 байта), данные. Длинные данные режутся на CONTINUE (0x003C).
- Сами картинки лежат в записях MSODRAWINGGROUP (0x00EB): это Escher-поток
  с хранилищем BLIP (по одной картинке на BSE, PNG или JPEG). Порядок
  хранилища и есть индекс картинки (pib, с единицы).
- Фигуры листа лежат в записях MSODRAWING (0x00EC): у каждой фигуры OPT
  (0xF00B) со свойством pib (0x0104, номер картинки) и ClientAnchor (0xF010)
  со строкой и колонкой ячейки, к которой картинка прибита.

Одна и та же картинка может стоять в нескольких строках (сорт в двух
размерах): pib у фигур совпадает, картинка одна. Логотип в шапке тоже фигура,
он отсеивается по строке: вызывающая сторона берёт только строки с данными.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

BIFF_CONTINUE = 0x003C
BIFF_MSODRAWINGGROUP = 0x00EB
BIFF_MSODRAWING = 0x00EC

ESCHER_OPT = 0xF00B
ESCHER_CLIENT_ANCHOR = 0xF010
ESCHER_PROP_PIB = 0x0104

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
# Три байта FF D8 FF встречаются и внутри сжатых данных PNG: настоящий JPEG
# продолжается маркером сегмента (APPn, DQT, SOFn, COM), по нему и отличаем.
PICTURE_START_RE = re.compile(
    b"(" + re.escape(PNG_MAGIC) + b"|" + re.escape(JPEG_MAGIC) + b"[\xc0-\xcf\xdb\xe0-\xef\xfe])"
)


def _biff_records(stream: bytes):
    """Записи BIFF подряд: (тип, данные). CONTINUE отдаём как есть, склеивает вызывающий."""
    pos = 0
    size = len(stream)
    while pos + 4 <= size:
        rtype, length = struct.unpack_from("<HH", stream, pos)
        pos += 4
        yield rtype, stream[pos : pos + length]
        pos += length


def _escher_streams(stream: bytes) -> tuple[bytes, bytes]:
    """Склеенные Escher-потоки: (хранилище картинок, фигуры листа)."""
    group: list[bytes] = []
    drawing: list[bytes] = []
    target = None
    for rtype, data in _biff_records(stream):
        if rtype == BIFF_MSODRAWINGGROUP:
            target = group
        elif rtype == BIFF_MSODRAWING:
            target = drawing
        elif rtype != BIFF_CONTINUE:
            target = None
            continue
        if target is not None:
            target.append(data)
    return b"".join(group), b"".join(drawing)


def _blips(group: bytes) -> list[bytes]:
    """Картинки хранилища в порядке BSE: PNG до IEND, JPEG до маркера конца."""
    starts = [m.start() for m in PICTURE_START_RE.finditer(group)]
    pictures: list[bytes] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(group)
        blob = group[start:end]
        if blob.startswith(PNG_MAGIC):
            tail = blob.find(b"IEND")
            blob = blob[: tail + 8] if tail >= 0 else blob
        else:
            tail = blob.rfind(b"\xff\xd9")
            blob = blob[: tail + 2] if tail >= 0 else blob
        pictures.append(blob)
    return pictures


def _shapes(drawing: bytes) -> list[tuple[int, int, int]]:
    """(pib, строка, колонка) для каждой фигуры с картинкой."""
    shapes: list[tuple[int, int, int]] = []
    pos = 0
    size = len(drawing)
    pending_pib: int | None = None
    while pos + 8 <= size:
        verinst, rtype, length = struct.unpack_from("<HHI", drawing, pos)
        is_container = (verinst & 0x0F) == 0x0F
        body_start = pos + 8
        if rtype == ESCHER_OPT:
            count = verinst >> 4
            pending_pib = None
            for i in range(count):
                offset = body_start + 6 * i
                if offset + 6 > size:
                    break
                prop_id, value = struct.unpack_from("<HI", drawing, offset)
                if prop_id & 0x3FFF == ESCHER_PROP_PIB:
                    pending_pib = value
        elif rtype == ESCHER_CLIENT_ANCHOR:
            if pending_pib and body_start + 18 <= size:
                _flag, col1, _dx1, row1, _dy1 = struct.unpack_from("<5H", drawing, body_start)
                shapes.append((pending_pib, row1, col1))
            pending_pib = None
        pos = body_start if is_container else body_start + length
    return shapes


def pictures_by_row(path: str | Path) -> dict[int, bytes]:
    """Картинка каждой строки листа: {номер строки (с нуля, как в xlrd): байты}.

    Файл без картинок или не xls - пустой словарь, а не исключение: прайс
    без фото импортировать всё равно надо.
    """
    try:
        import olefile
    except ImportError:  # pragma: no cover - зависимость в requirements
        return {}
    try:
        ole = olefile.OleFileIO(str(path))
    except Exception:  # noqa: BLE001 - не OLE-файл
        return {}
    try:
        if not ole.exists("Workbook"):
            return {}
        stream = ole.openstream("Workbook").read()
    finally:
        ole.close()

    group, drawing = _escher_streams(stream)
    blips = _blips(group)
    result: dict[int, bytes] = {}
    for pib, row, _col in _shapes(drawing):
        if 1 <= pib <= len(blips) and row not in result:
            result[row] = blips[pib - 1]
    return result

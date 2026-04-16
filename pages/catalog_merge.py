"""
Объединение дублей каталога в одну карточку с вариантами формата.

Правило: внутри одной категории товары с одинаковым базовым названием (без хвоста
формата/высоты вида «: C15, h=100-120», «... Р9» или «... Кашпо 5л») объединяются в одну карточку.
"""
from __future__ import annotations

import copy
import re
from collections import defaultdict
from typing import Any

FORMAT_VARIANTS_NOTE = (
    "Формат посадки: в контейнере С2/3 или С3 растение с более развитой корневой "
    "системой и крупнее надземная часть — быстрее приживется и даст прирост уже в первый сезон. "
    "В P9/Р9 — моложе (часто черенок или сеянец), в первый год нужен аккуратный уход, зато дешевле."
)

FORMAT_TAIL_RE = re.compile(
    r"^\s*"
    r"(?P<container>[PРCС]\s*\d+(?:[.,/]\d+)?)?"
    r"\s*,?\s*"
    r"(?P<height>h\s*=?\s*\d+(?:[-–]\d+)?\*?)?"
    r"\s*$",
    re.IGNORECASE,
)
TRAILING_CONTAINER_RE = re.compile(r"\s+(?:[PРCС]\s*\d+(?:/\d+)?)\s*$", re.IGNORECASE)
TRAILING_HEIGHT_RE = re.compile(r"\s*,?\s*h\s*=?\s*\d+(?:[-–]\d+)?\*?\s*$", re.IGNORECASE)
# «… Кашпо 5л», «… кашпо 5,5 л» — хвост формата для группировки с P9/Р9 и т.п.
TRAILING_KASHPO_RE = re.compile(r"\s+кашпо\s*[\d.,/]+\s*л\b", re.IGNORECASE)
TRAILING_COMPLEX_RE = re.compile(
    r"(?:"
    r"(?:[PРCС]\s*\d+(?:[.,/]\d+)?)\s*,?\s*(?:h\s*=?\s*\d+(?:[-–]\d+)?\*?)"
    r"|"
    r"(?:h\s*=?\s*\d+(?:[-–]\d+)?\*?)\s*(?:[PРCС]\s*\d+(?:[.,/]\d+)?)"
    r"|"
    r"(?:h\s*=?\s*\d+(?:[-–]\d+)?\*?)\s*[PРCС]\s*\d+(?:[.,/]\d+)?"
    r")\s*$",
    re.IGNORECASE,
)


def _price_num(p: dict[str, Any]) -> int:
    try:
        v = p.get("variants") or [{}]
        pr = str(v[0].get("price") or "0")
        digits = re.sub(r"\D", "", pr)
        return int(digits or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _split_name_base_and_tail(name: str) -> tuple[str, str]:
    s = _normalize_spaces(name)
    if " : " in s:
        left, right = s.rsplit(" : ", 1)
        if (not right.strip()) or FORMAT_TAIL_RE.match(right):
            return _normalize_spaces(left), _normalize_spaces(right)
    m3 = TRAILING_COMPLEX_RE.search(s)
    if m3:
        base = _normalize_spaces(s[: m3.start()])
        tail = _normalize_spaces(s[m3.start() :]).lstrip(",").strip()
        return base, tail
    m = TRAILING_CONTAINER_RE.search(s)
    if m:
        base = _normalize_spaces(s[: m.start()])
        tail = _normalize_spaces(s[m.start() :])
        return base, tail
    m2 = TRAILING_HEIGHT_RE.search(s)
    if m2:
        base = _normalize_spaces(s[: m2.start()])
        tail = _normalize_spaces(s[m2.start() :]).lstrip(",").strip()
        return base, tail
    m_k = TRAILING_KASHPO_RE.search(s)
    if m_k:
        base = _normalize_spaces(s[: m_k.start()])
        tail = _normalize_spaces(s[m_k.start() :]).strip()
        return base, tail
    return s, ""


def _normalized_group_key(p: dict[str, Any]) -> tuple[str, str]:
    cat = str((p.get("category_slug") or "")).strip()
    base, _ = _split_name_base_and_tail(str(p.get("name") or ""))
    base = re.sub(r"\s*[:;,.-]+\s*$", "", base or "").strip()
    return cat, base.lower()


def _container_from_text(text: str) -> str:
    raw = text or ""
    mk = re.search(r"кашпо\s*([\d.,/]+)\s*л\b", raw, re.IGNORECASE)
    if mk:
        vol = mk.group(1).replace(".", ",")
        return f"Кашпо {vol}л"
    m = re.search(r"([PРCСp]\s*\d+(?:[.,/]\d+)?)", raw, flags=re.IGNORECASE)
    if not m:
        return "формат уточняйте"
    t = m.group(1).replace(" ", "")
    first = t[0]
    num = t[1:]
    if first in ("c", "с", "C", "С"):
        return f"С{num.replace('.', ',')}"
    if first in ("r", "р", "R", "Р"):
        return f"Р{num.replace('.', ',')}"
    return f"P{num.replace('.', ',')}"


def _height_from_text(text: str) -> str:
    m = re.search(r"h\s*=?\s*(\d+(?:[-–]\d+)?)", text or "", flags=re.IGNORECASE)
    if not m:
        return "уточняйте"
    return f"h={m.group(1).replace('–', '-')}"


def _unknown(v: str) -> bool:
    x = (v or "").strip().lower()
    return (not x) or ("уточня" in x) or ("формат" in x and "уточня" in x) or ("выберите" in x)


def _variant_from_member(member: dict[str, Any], v0: dict[str, Any], fallback_tail: str) -> dict[str, Any]:
    name_tail = _split_name_base_and_tail(str(member.get("name") or ""))[1]
    detail = name_tail or fallback_tail
    raw_container = str(v0.get("container") or "").strip()
    raw_height = str(v0.get("height") or "").strip()
    return {
        "height": _height_from_text(detail) if _unknown(raw_height) else raw_height,
        "container": _container_from_text(detail) if _unknown(raw_container) else raw_container,
        "price": str(v0.get("price") or "—").strip(),
        "in_stock": bool(v0.get("in_stock", True)),
    }


def _catalog_teaser_bundle(n_variants: int, min_price: int) -> tuple[str, str, str]:
    line2 = "(высота и формат)"
    # Нет числовой цены в данных (часто «уточняйте» на старом сайте) — без «от … ₽»
    if min_price <= 0:
        line1 = f"уточняйте · {n_variants} вариант(-а)"
    else:
        price_s = f"{min_price:,}".replace(",", " ")
        line1 = f"от {price_s} ₽ · {n_variants} вариант(-а)"
    return f"{line1} {line2}", line1, line2


def _union_paths(plants: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for p in plants:
        for lp in p.get("legacy_paths") or []:
            s = str(lp)
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def _union_also(plants: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for p in plants:
        for x in p.get("also_in_category_slugs") or []:
            s = str(x)
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def _build_merged_plant(group: list[dict[str, Any]]) -> dict[str, Any]:
    canonical = max(group, key=_price_num)
    merged = copy.deepcopy(canonical)

    members_sorted = sorted(group, key=_price_num, reverse=True)
    variants_out: list[dict[str, Any]] = []
    seen_variant_keys: set[tuple[str, str, str]] = set()
    for m in members_sorted:
        fallback_tail = str(m.get("slug") or "").split("-")[-1]
        source_variants = list(m.get("variants") or [])
        if not source_variants:
            source_variants = [{}]
        for v0 in source_variants:
            vv = _variant_from_member(m, v0, fallback_tail)
            key = (vv["container"], vv["height"], vv["price"])
            if key in seen_variant_keys:
                continue
            seen_variant_keys.add(key)
            variants_out.append(vv)

    aliases = [p["slug"] for p in group if p["slug"] != merged["slug"]]
    clean_name, _ = _split_name_base_and_tail(canonical.get("name") or "")
    merged["name"] = clean_name
    merged["variants"] = variants_out or merged.get("variants") or []
    merged["merged_member_slugs"] = aliases
    merged["merged_format_group"] = True
    merged["format_variants_note"] = FORMAT_VARIANTS_NOTE
    merged["pv_field_labels"] = {"height": "Высота", "container": "Формат посадки"}
    merged["legacy_paths"] = _union_paths(group)
    merged["also_in_category_slugs"] = _union_also(group)

    prices = [_price_num({"variants": [x]}) for x in (variants_out or [{}])]
    mn = min(prices) if prices else 0
    full, price_line, variant_line = _catalog_teaser_bundle(len(variants_out or [1]), mn)
    merged["catalog_teaser"] = full
    merged["catalog_price_line"] = price_line
    merged["catalog_variant_line"] = variant_line
    return merged


def get_merged_catalog_plants() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Список растений после объединения + map алиас slug -> канонический slug."""
    from pages.data import CATALOG_PAGE

    unmerged: list[dict[str, Any]] = list(CATALOG_PAGE.get("plants") or [])
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for p in unmerged:
        by_key[_normalized_group_key(p)].append(p)

    result: list[dict[str, Any]] = []
    redirects: dict[str, str] = {}
    for _, group in by_key.items():
        if len(group) < 2:
            result.extend(group)
            continue
        merged = _build_merged_plant(group)
        result.append(merged)
        for p in group:
            if p.get("slug") and p["slug"] != merged.get("slug"):
                redirects[p["slug"]] = str(merged.get("slug") or p["slug"])

    return result, redirects


def resolve_catalog_plant_slug(slug: str) -> str:
    _, redirects = get_merged_catalog_plants()
    return redirects.get(slug, slug)


def find_merged_plant(merged: list[dict[str, Any]], slug: str) -> dict[str, Any] | None:
    for p in merged:
        if p.get("slug") == slug:
            return p
        if slug in (p.get("merged_member_slugs") or []):
            return p
    return None

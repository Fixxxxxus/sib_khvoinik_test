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
# «(Ком+сетка d=600)», «(ком+сетка)» — в тару, не в заголовок витрины
KOM_SETKA_IN_PARENS_RE = re.compile(
    r"\s*\(\s*ком\s*\+\s*сетка(?:\s*,?\s*d\s*=\s*([\d.,/]+))?\s*\)",
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


def _strip_kom_setka_and_name_height(s: str) -> str:
    """Убираем из названия (ком+сетка …) и хвост высоты h=… / h … в конце."""
    t = KOM_SETKA_IN_PARENS_RE.sub("", s or "")
    t = re.sub(r"(?i)(?:,\s*|\s+)h\s*=\s*[\d.,]+\s*(?:[-–]\s*[\d.,]+)?\s*$", "", t)
    t = re.sub(r"(?i)(?:,\s*|\)\s*)h\s+[\d.,]+\s*(?:[-–]\s*[\d.,]+)?\s*$", "", t)
    # «…" сорт" h 2,0-2,5» после снятия скобок с ком+сетка
    t = re.sub(r"(?i)\s+h\s+[\d.,]+\s*(?:[-–]\s*[\d.,]+)?\s*$", "", t)
    t = re.sub(r"\s*,\s*$", "", t)
    return _normalize_spaces(t)


def _kom_setka_label_from_name(raw_name: str) -> str | None:
    m = KOM_SETKA_IN_PARENS_RE.search(raw_name or "")
    if not m:
        return None
    d = m.group(1)
    if d:
        return f"ком+сетка d={str(d).strip()}"
    return "ком+сетка"


def _kom_setka_label_from_legacy(legacy_paths: list[Any] | None) -> str | None:
    if not legacy_paths:
        return None
    blob = " ".join(str(p) for p in legacy_paths).lower()
    m = re.search(r"kom_setka_d_(\d+)", blob)
    if m:
        return f"ком+сетка d={m.group(1)}"
    return None


def _height_tail_from_product_name(raw_name: str) -> str | None:
    """Высота из хвоста названия: «, h=2.0-2.5», «) h 2,0-2,5» или «" сорт" h 2,0-2,5»."""
    s = (raw_name or "").strip()
    if not s:
        return None
    m = re.search(r"(?i)(?:,\s*|\)\s*|\s+)h\s*=\s*([\d.,]+(?:\s*[-–]\s*[\d.,]+)?)\s*$", s)
    if not m:
        m = re.search(r"(?i)(?:,\s*|\)\s*)h\s+([\d.,]+(?:\s*[-–]\s*[\d.,]+)?)\s*$", s)
    if not m:
        m = re.search(r"(?i)\s+h\s+([\d.,]+(?:\s*[-–]\s*[\d.,]+)?)\s*$", s)
    if not m:
        return None
    val = m.group(1).replace("–", "-").replace(" ", "")
    parts = val.split("-")
    norm_parts: list[str] = []
    for part in parts:
        p = part.strip()
        if re.match(r"^\d+,\d+$", p):
            norm_parts.append(p.replace(",", "."))
        else:
            norm_parts.append(p.replace(",", "."))
    return f"h={'-'.join(norm_parts)}"


def hydrate_variants_kom_setka_height_from_name(plant: dict[str, Any]) -> None:
    """Заполняем container/height в variants из полного названия и legacy (КОМ+сетка, h=…)."""
    raw_name = str(plant.get("name") or "")
    kom = _kom_setka_label_from_name(raw_name)
    if not kom:
        slug_l = str(plant.get("slug") or "").lower()
        if "kom-setka" in slug_l:
            kom = _kom_setka_label_from_legacy(plant.get("legacy_paths"))
    htm = _height_tail_from_product_name(raw_name)
    bare_kom_cf = re.sub(r"\s+", "", "ком+сетка").casefold()
    for v in plant.get("variants") or []:
        if not isinstance(v, dict):
            continue
        if kom:
            cv = str(v.get("container") or "").strip()
            cv_cf = re.sub(r"\s+", "", cv).casefold()
            if _unknown(cv) or cv_cf == bare_kom_cf:
                v["container"] = kom
        hv = str(v.get("height") or "").strip()
        if htm and _unknown(hv):
            v["height"] = htm


def _split_name_base_and_tail(name: str) -> tuple[str, str]:
    s = _strip_kom_setka_and_name_height(_normalize_spaces(name))
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


def _legacy_paths_matching_variant_height(paths: list[str], height_str: str) -> list[str]:
    """Сопоставляем вариант (h 30-50, h=60-80) с фрагментом slug вида h_30_50 / h-30-50."""
    h = (height_str or "").strip().lower()
    m = re.search(r"h\s*=?\s*(\d+)(?:[-–](\d+))?", h)
    if not m:
        return []
    lo, hi = m.group(1), m.group(2) or m.group(1)
    needles = (f"h_{lo}_{hi}", f"h-{lo}-{hi}")
    out: list[str] = []
    for p in paths:
        pl = p.lower()
        if any(n in pl for n in needles):
            out.append(p)
    return out


def infer_container_from_legacy_paths(
    legacy_paths: list[Any] | None, *, variant_height: str | None = None
) -> str | None:
    """Достаём тару из URL старого сайта, если в карточке было «формат уточняйте»."""
    paths = [str(p) for p in (legacy_paths or []) if p]
    if not paths:
        return None
    if len(paths) > 1 and (variant_height or "").strip():
        matched = _legacy_paths_matching_variant_height(paths, variant_height or "")
        if matched:
            paths = matched
        else:
            return None
    blob = " ".join(paths).lower()
    mk = re.search(r"kashpo[_\s]*([\d.,/]+)\s*l", blob)
    if mk:
        return f"Кашпо {mk.group(1).replace('.', ',')}л"
    if re.search(r"(?:^|[_/])(?:p|r)9(?:[_/]|$)", blob):
        return "Р9"
    if re.search(r"(?:s2[_\s]*3|s_2_3|c2[_\s]*3)(?:[_/]|$)", blob):
        return "С2/3"
    if re.search(r"s5[_\s]*7[_\s]*5", blob) or "s5-7-5" in blob:
        return "С5-7,5"
    if re.search(r"[_/]s5(?:[_/]|$)", blob) or re.search(r"_h_\d.*_s5", blob):
        return "С5"
    return None


def normalize_plant_variants_legacy_containers(plant: dict[str, Any]) -> None:
    """Подставляем тару из legacy_paths в variants[].container (на месте копии каталога)."""
    for v in plant.get("variants") or []:
        if not isinstance(v, dict):
            continue
        c = str(v.get("container") or "").strip()
        if not _unknown(c):
            continue
        inf = infer_container_from_legacy_paths(
            plant.get("legacy_paths"),
            variant_height=str(v.get("height") or "").strip() or None,
        )
        if inf:
            v["container"] = inf


def split_russian_latin_title(name: str) -> tuple[str, str]:
    """Крупный русский заголовок + мелкая латиница (сортовое название)."""
    s = _normalize_spaces(name)
    if not s:
        return "", ""
    m = re.search(
        r"^(?P<ru>.+?)\s+"
        r'(?P<lat>(?:[A-Z][a-z]+\.\s+)?[A-Z][a-z]+'
        r'(?:\s*[×\u00d7x]\s+[A-Za-z][a-z0-9\-]*)?'
        r'(?:\s+[A-Za-z][a-z0-9\-]*)*'
        r'(?:\s+[\"«][^\"»\n]{1,120}[\"»])?)\s*$',
        s,
    )
    if m:
        return m.group("ru").strip(), m.group("lat").strip()
    return s, ""


def _variant_from_member(member: dict[str, Any], v0: dict[str, Any], fallback_tail: str) -> dict[str, Any]:
    name_tail = _split_name_base_and_tail(str(member.get("name") or ""))[1]
    detail = name_tail or fallback_tail
    raw_container = str(v0.get("container") or "").strip()
    raw_height = str(v0.get("height") or "").strip()
    if _unknown(raw_container):
        inferred = infer_container_from_legacy_paths(
            member.get("legacy_paths"),
            variant_height=raw_height or None,
        )
        if inferred:
            raw_container = inferred
    return {
        "height": _height_from_text(detail) if _unknown(raw_height) else raw_height,
        "container": _container_from_text(detail) if _unknown(raw_container) else raw_container,
        "price": str(v0.get("price") or "—").strip(),
        "in_stock": bool(v0.get("in_stock", True)),
    }


def _unique_containers_ordered(variants: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in variants or []:
        if not isinstance(v, dict):
            continue
        c = str(v.get("container") or "").strip()
        if _unknown(c):
            continue
        key = c.casefold()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _is_odnoletnie_rassada_category(category_slug: str) -> bool:
    c = (category_slug or "").strip()
    return c == "odnoletniaia-rassada" or c.startswith("odnoletnie-")


def _variant_container_is_p9_or_kashpo(container: str) -> bool:
    """Р9/кашпо — отдельная фасовка, без правила «кассета N ячеек»."""
    s = (container or "").strip()
    if not s or _unknown(s):
        return False
    if "кашпо" in s.casefold():
        return True
    return bool(re.search(r"(?i)[pр]\s*9\b", s))


def _apply_odnoletnie_rassada_packaging_rules(plant: dict[str, Any]) -> None:
    """Без P9/Кашпо — «кассета из 6 ячеек»; в подборе — кратно 6 (selection_qty_step)."""
    plant.pop("odnoletnie_pack_note", None)
    if not _is_odnoletnie_rassada_category(str(plant.get("category_slug") or "")):
        return
    vars_ = [v for v in (plant.get("variants") or []) if isinstance(v, dict)]
    if not vars_:
        return
    if any(_variant_container_is_p9_or_kashpo(str(v.get("container") or "")) for v in vars_):
        return
    for v in vars_:
        c = str(v.get("container") or "").strip()
        if _unknown(c):
            v["container"] = "кассета из 6 ячеек"
    plant["selection_qty_step"] = 6


def _legacy_paths_indicate_ovoshchi_4cell_cassette(legacy_paths: list[Any] | None) -> bool:
    """Огурец / тыква / кабачок / арбуз-дыня по URL старого каталога."""
    blob = " ".join(str(p).lower() for p in (legacy_paths or []) if p)
    return any(
        needle in blob
        for needle in ("/ogurtsy/", "/tykvy/", "/kabachki/", "/arbuz_dynya/")
    )


def _apply_ovoshchnaya_rassada_4cell_packaging_rules(plant: dict[str, Any]) -> None:
    """Огурец, тыква, кабачок, арбуз/дыня — кассета из 4 ячеек; подбор кратно 4."""
    if str(plant.get("category_slug") or "").strip() != "ovoshchnaya-rassada":
        return
    if not _legacy_paths_indicate_ovoshchi_4cell_cassette(plant.get("legacy_paths")):
        return
    vars_ = [v for v in (plant.get("variants") or []) if isinstance(v, dict)]
    if not vars_:
        return
    if any(_variant_container_is_p9_or_kashpo(str(v.get("container") or "")) for v in vars_):
        return
    for v in vars_:
        c = str(v.get("container") or "").strip()
        if _unknown(c):
            v["container"] = "кассета из 4 ячеек"
    plant["selection_qty_step"] = 4


def _catalog_listing_bundle(variants: list[dict[str, Any]]) -> tuple[str, str, str]:
    """Цена для сетки каталога, строка тары, объединённый тизер для кнопок/форм."""
    vars_eff = variants if variants else [{}]
    n = max(1, len(variants or []))
    prices = [_price_num({"variants": [x]}) for x in vars_eff]
    mn = min(prices) if prices else 0
    containers = _unique_containers_ordered(list(variants or []))
    container_line = " · ".join(containers) if containers else ""
    if mn <= 0:
        price_line = "уточняйте"
    else:
        ps = f"{mn:,}".replace(",", " ")
        price_line = f"от {ps} ₽" if n > 1 else f"{ps} ₽"
    teaser = price_line + (f" · {container_line}" if container_line else "")
    return teaser, price_line, container_line


def apply_catalog_display_fields(plant: dict[str, Any]) -> None:
    """Имя без тары на витрине, цена/тара для сетки, подпись кассеты для однолетников."""
    plant.pop("selection_qty_step", None)
    hydrate_variants_kom_setka_height_from_name(plant)
    normalize_plant_variants_legacy_containers(plant)
    _apply_odnoletnie_rassada_packaging_rules(plant)
    _apply_ovoshchnaya_rassada_4cell_packaging_rules(plant)
    base, _tail = _split_name_base_and_tail(str(plant.get("name") or ""))
    plant["catalog_display_name"] = (base or str(plant.get("name") or "")).strip()
    ru, lat = split_russian_latin_title(plant["catalog_display_name"])
    plant["title_ru"] = ru
    plant["title_latin"] = lat
    vars_ = list(plant.get("variants") or [])
    if vars_:
        teaser, price_line, container_line = _catalog_listing_bundle(vars_)
        plant["catalog_teaser"] = teaser
        plant["catalog_price_line"] = price_line
        plant["catalog_container_line"] = container_line
        plant["catalog_variant_line"] = container_line
    else:
        plant.pop("catalog_price_line", None)
        plant.pop("catalog_container_line", None)
        plant.pop("catalog_variant_line", None)


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

    return merged


def get_merged_catalog_plants() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Список растений после объединения + map алиас slug -> канонический slug."""
    from pages.data import CATALOG_PAGE

    unmerged: list[dict[str, Any]] = [copy.deepcopy(p) for p in (CATALOG_PAGE.get("plants") or [])]
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for p in unmerged:
        by_key[_normalized_group_key(p)].append(p)

    result: list[dict[str, Any]] = []
    redirects: dict[str, str] = {}
    for _, group in by_key.items():
        if len(group) < 2:
            for p in group:
                apply_catalog_display_fields(p)
                result.append(p)
            continue
        merged = _build_merged_plant(group)
        apply_catalog_display_fields(merged)
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

"""
Навигация каталога — структура бокового меню как на old.gazony.ru.
В левой панели только уровень вида/класса (роды, группы), без сортов и торговых карточек.
Подсветка и раскрытие: по active_plant_slug / active_category_slug и по категории товара.
"""

from __future__ import annotations

from typing import Any


def _soon(label: str) -> dict[str, Any]:
    return {"label": label, "soon": True}


def _link(label: str, catalog_slug: str) -> dict[str, Any]:
    return {"label": label, "catalog_slug": catalog_slug}


# --- Кустарники ---
_KUSTARNIKI_CHILDREN: list[dict[str, Any]] = [
    _link("Все кустарники", "listvennye-kustarniki"),
    _soon("Бересклет"),
    _soon("Барбарис"),
    _soon("Бирючина"),
    _soon("Гортензия"),
    _soon("Дерен"),
    _soon("Жимолость"),
    _soon("Калина"),
    _soon("Кизильник"),
    _soon("Лапчатка"),
    _soon("Лох"),
    _soon("Миндаль"),
    {
        "label": "Пузыреплодник",
        "catalog_slug": "puzyreplodnik",
        "match_slugs": ["puzyreplodnik-luteus"],
    },
    _soon("Роза морщинистая"),
    _soon("Рябинник"),
    _soon("Сирень"),
    _soon("Смородина альпийская"),
    _soon("Снежноягодник"),
    _soon("Спирея"),
    _soon("Чубушник"),
]

# --- Однолетние цветы (полный список со старого меню) ---
_ODNOLETNIE_CHILDREN: list[dict[str, Any]] = [
    _link("Все однолетние цветы", "odnoletniaia-rassada"),
    _soon("Агератум"),
    _soon("Ампельные"),
    _soon("Вербена"),
    _soon("Виола"),
    _soon("Гацания"),
    _soon("Георгина"),
    _soon("Гипоэстес"),
    _soon("Колеус"),
    _soon("Лобелия"),
    _soon("Петуния"),
    _soon("Алиссиум"),
    _soon("Кохия"),
    _soon("Сальвия"),
    _soon("Львиный зев (Антирринум)"),
    _soon("Цинерария"),
    _soon("Бархатцы"),
]

# --- Деревья ---
_DEREVYA_CHILDREN: list[dict[str, Any]] = [
    _link("Все деревья", "derevya"),
    _soon("Дуб"),
    _soon("Вяз"),
    _soon("Клён"),
    _soon("Рябина"),
    _soon("Черёмуха"),
    _soon("Яблоня декоративная"),
]

# --- Многолетние цветы (два блока списка со скринов, объединены) ---
_MNOGOLETNIE_CHILDREN: list[dict[str, Any]] = [
    _link("Все многолетние цветы", "mnogoletnie-tsvety"),
    _soon("Аквилегия"),
    _soon("Бруннера"),
    _soon("Герань"),
    _soon("Пион"),
    _soon("Анемона"),
    _soon("Гортензия крупнолистная"),
    _soon("Ирисы"),
    _soon("Клематис"),
    _soon("Обриета"),
    _soon("Платикодон"),
    _soon("Армерия"),
    _soon("Гвоздика"),
    _soon("Кореопсис"),
    _soon("Люпин"),
    _soon("Барвинок"),
    _soon("Гайлардия"),
    _soon("Штокроза"),
    _soon("Гелениум"),
    _soon("Эхинацея"),
    _soon("Гравилат"),
    _soon("Дельфиниум"),
    _soon("Колокольчик"),
    _soon("Купальница"),
    _soon("Ландыш майский"),
    _soon("Лапчатка"),
    _soon("Лилейник"),
    _soon("Астильба"),
    _soon("Астра"),
    _soon("Бадан"),
    _soon("Вероника/Вероникаструм"),
    _soon("Гейхера"),
    _soon("Дербенник"),
    _soon("Злаки"),
    _soon("Монарда"),
    _soon("Нивянник"),
    _soon("Прочие"),
    _soon("Пряно-декоративные травы"),
    _soon("Седум"),
    _soon("Тысячелистник"),
    _soon("Флокс"),
    _soon("Хоста"),
    _soon("Хризантема"),
]

# --- Овощная рассада ---
_OVOSHCHI_CHILDREN: list[dict[str, Any]] = [
    _link("Вся овощная рассада", "ovoshchnaya-rassada"),
    _soon("Тыквы"),
    _soon("Баклажаны"),
    _soon("Томаты"),
    _soon("Арбуз/Дыня"),
    _soon("Кабачки"),
    _soon("Огурцы"),
    _soon("Перцы"),
]

# --- Плодовые ---
_PLODOVYE_CHILDREN: list[dict[str, Any]] = [
    _link("Все плодовые", "plodovye"),
    _soon("Вишня"),
    _soon("Груша"),
    _soon("Жимолость"),
    _soon("Малина"),
    _soon("Облепиха"),
    _soon("Слива/СВГ"),
    _soon("Смородина"),
    _soon("Яблоня"),
]

# --- Розы ---
_ROZY_CHILDREN: list[dict[str, Any]] = [
    _link("Все розы", "rozy"),
    _soon("Английские"),
    _soon("Плетистые"),
    _soon("Спрей"),
    _soon("Флорибунда"),
    _soon("Чайно-гибридные"),
    _soon("Шрабы"),
]

# --- Семена газонных трав ---
_SEMENA_CHILDREN: list[dict[str, Any]] = [
    _link("Все семена газонных трав", "semena-gazonnyh-trav"),
    _soon("Газонная травосмесь Гринкипер"),
    _soon("Газонная травосмесь Зеленый ковер/Канада"),
]

# --- Хвойные: только роды/группы, без карточек «ель сибирская», «туя западная» и т.п. ---
_KHOYNYE_CHILDREN: list[dict[str, Any]] = [
    _link("Все хвойные", "hvoynye-derevya"),
    _soon("Лиственница"),
    _soon("Ель колючая"),
    _soon("Можжевельник"),
    _soon("Пихта"),
    _soon("Сосна"),
    _soon("Туя"),
]

# Раскрывать раздел, если открыта эта категория каталога или карточка товара из неё
_SECTION_EXPAND_CATEGORIES: dict[str, frozenset[str]] = {
    "Кустарники": frozenset({"listvennye-kustarniki", "puzyreplodnik"}),
    "Деревья": frozenset({"derevya"}),
    "Хвойные": frozenset({"hvoynye-derevya"}),
    "Однолетние цветы": frozenset({"odnoletniaia-rassada", "rassada-odnoletniaia-ovoshchi"}),
    "Овощная рассада": frozenset({"ovoshchnaya-rassada", "rassada-odnoletniaia-ovoshchi"}),
    "Многолетние цветы": frozenset({"mnogoletnie-tsvety"}),
    "Плодовые": frozenset({"plodovye"}),
    "Розы": frozenset({"rozy"}),
    "Семена газонных трав": frozenset({"semena-gazonnyh-trav"}),
}

CATALOG_NAV_SECTIONS_RAW: list[dict[str, Any]] = [
    {"label": "Рулонные газоны", "icon": "layers", "named_url": "gazon"},
    {"label": "Клубника", "icon": "cherry", "catalog_slug": "klubnika"},
    {"label": "Однолетние цветы", "icon": "flower-2", "children": _ODNOLETNIE_CHILDREN},
    {"label": "Деревья", "icon": "tree-deciduous", "children": _DEREVYA_CHILDREN},
    {"label": "Кустарники", "icon": "trees", "children": _KUSTARNIKI_CHILDREN},
    {"label": "Многолетние цветы", "icon": "leaf", "children": _MNOGOLETNIE_CHILDREN},
    {"label": "Овощная рассада", "icon": "carrot", "children": _OVOSHCHI_CHILDREN},
    {"label": "Плодовые", "icon": "apple", "children": _PLODOVYE_CHILDREN},
    {"label": "Розы", "icon": "rose", "children": _ROZY_CHILDREN},
    {"label": "Семена газонных трав", "icon": "wheat", "children": _SEMENA_CHILDREN},
    {"label": "Хвойные", "icon": "tree-pine", "children": _KHOYNYE_CHILDREN},
]


def _active_category_slug(ctx: dict, active_plant_slug: str) -> str:
    ac = (ctx.get("active_category_slug") or "").strip()
    if ac:
        return ac
    if not active_plant_slug:
        return ""
    for p in ctx.get("plants") or []:
        if p.get("slug") == active_plant_slug:
            return (p.get("category_slug") or "").strip()
    return ""


def enrich_catalog_context(ctx: dict) -> dict:
    from django.urls import reverse

    active = (ctx.get("active_plant_slug") or ctx.get("active_category_slug") or "").strip()
    active_cat = _active_category_slug(ctx, active)

    def resolve(raw: dict[str, Any]) -> dict[str, Any]:
        children_in = raw.get("children")
        item: dict[str, Any] = {
            "label": raw["label"],
            "icon": raw.get("icon") or "sprout",
            "soon": bool(raw.get("soon")),
        }
        if raw.get("match_slugs"):
            item["match_slugs"] = list(raw["match_slugs"])

        if children_in:
            item["children"] = [resolve(c) for c in children_in]
            return item

        if raw.get("named_url"):
            item["href"] = reverse(raw["named_url"])
        elif raw.get("catalog_slug"):
            item["href"] = reverse("catalog_item", kwargs={"slug": raw["catalog_slug"]})
            item["nav_slug"] = raw["catalog_slug"]
        return item

    sections: list[dict[str, Any]] = [resolve(s) for s in CATALOG_NAV_SECTIONS_RAW]

    def child_is_active(child: dict[str, Any]) -> bool:
        if child.get("soon"):
            return False
        if active and active in (child.get("match_slugs") or []):
            return True
        nav_slug = child.get("nav_slug")
        return bool(active and nav_slug and nav_slug == active)

    def section_is_active(sec: dict[str, Any]) -> bool:
        if sec.get("soon"):
            return False
        if active and active in (sec.get("match_slugs") or []):
            return True
        nav_slug = sec.get("nav_slug")
        return bool(active and nav_slug and nav_slug == active)

    for sec in sections:
        children = sec.get("children")
        if children:
            for c in children:
                c["nav_active"] = child_is_active(c)
            any_open = any(c.get("nav_active") for c in children)
            sec["nav_expanded"] = any_open
            sec["nav_parent_active"] = any_open
        else:
            sec["nav_active"] = section_is_active(sec)
            sec["nav_expanded"] = False
            sec["nav_parent_active"] = False

    for sec in sections:
        need_cats = _SECTION_EXPAND_CATEGORIES.get(sec["label"])
        if need_cats and active_cat in need_cats and sec.get("children"):
            sec["nav_expanded"] = True
            sec["nav_parent_active"] = True

    out = dict(ctx)
    out["catalog_nav_sections"] = sections
    out["catalog_nav_active_slug"] = active
    return out

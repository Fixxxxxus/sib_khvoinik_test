"""
Навигация каталога — структура бокового меню как на old.gazony.ru.
В левой панели только уровень вида/класса (роды, группы), без сортов и торговых карточек.
Подсветка и раскрытие: по active_plant_slug / active_category_slug и по категории товара.
"""

from __future__ import annotations

from typing import Any


def _link(label: str, catalog_slug: str) -> dict[str, Any]:
    return {"label": label, "catalog_slug": catalog_slug}


# --- Кустарники ---
_KUSTARNIKI_CHILDREN: list[dict[str, Any]] = [
    _link("Все кустарники", "listvennye-kustarniki"),
    _link("Бересклет", "kustarniki-beresklet"),
    _link("Барбарис", "kustarniki-barbaris"),
    _link("Бирючина", "kustarniki-biryuchina"),
    _link("Гортензия", "kustarniki-gortenziya"),
    _link("Дерен", "kustarniki-deren"),
    _link("Жимолость", "kustarniki-zhimolost"),
    _link("Калина", "kustarniki-kalina"),
    _link("Кизильник", "kustarniki-kizilnik"),
    _link("Лапчатка", "kustarniki-lapchatka"),
    _link("Лох", "kustarniki-lokh"),
    _link("Миндаль", "kustarniki-mindal"),
    _link("Пузыреплодник", "kustarniki-puzyreplodnik"),
    _link("Роза морщинистая", "kustarniki-roza-morshchinistaya"),
    _link("Рябинник", "kustarniki-ryabinnik"),
    _link("Сирень", "kustarniki-siren"),
    _link("Смородина альпийская", "kustarniki-smorodina-alpiyskaya"),
    _link("Снежноягодник", "kustarniki-snezhnoyagodnik"),
    _link("Спирея", "kustarniki-spireya"),
    _link("Чубушник", "kustarniki-chubushnik"),
]

# --- Однолетние цветы (полный список со старого меню) ---
_ODNOLETNIE_CHILDREN: list[dict[str, Any]] = [
    _link("Все однолетние цветы", "odnoletniaia-rassada"),
    _link("Агератум", "odnoletnie-ageratum"),
    _link("Ампельные", "odnoletnie-ampelnye"),
    _link("Вербена", "odnoletnie-verbena"),
    _link("Виола", "odnoletnie-viola"),
    _link("Гацания", "odnoletnie-gatsaniya"),
    _link("Георгина", "odnoletnie-georgina"),
    _link("Гипоэстес", "odnoletnie-gipoestes"),
    _link("Колеус", "odnoletnie-koleus"),
    _link("Лобелия", "odnoletnie-lobeliya"),
    _link("Петуния", "odnoletnie-petuniya"),
    _link("Алиссиум", "odnoletnie-alissium"),
    _link("Кохия", "odnoletnie-kokhiya"),
    _link("Сальвия", "odnoletnie-salviya"),
    _link("Львиный зев (Антирринум)", "odnoletnie-lvinnyy-zev-antirrinum"),
    _link("Цинерария", "odnoletnie-tsinerariya"),
    _link("Бархатцы", "odnoletnie-barkhattsy"),
]

# --- Деревья ---
_DEREVYA_CHILDREN: list[dict[str, Any]] = [
    _link("Все деревья", "derevya"),
    _link("Дуб", "derevya-dub"),
    _link("Вяз", "derevya-vyaz"),
    _link("Клён", "derevya-klyen"),
    _link("Рябина", "derevya-ryabina"),
    _link("Черёмуха", "derevya-cheryemukha"),
    _link("Яблоня декоративная", "derevya-yablonya-dekorativnaya"),
]

# --- Многолетние цветы (два блока списка со скринов, объединены) ---
_MNOGOLETNIE_CHILDREN: list[dict[str, Any]] = [
    _link("Все многолетние цветы", "mnogoletnie-tsvety"),
    _link("Аквилегия", "mnogoletnie-akvilegiya"),
    _link("Бруннера", "mnogoletnie-brunnera"),
    _link("Герань", "mnogoletnie-geran"),
    _link("Пион", "mnogoletnie-pion"),
    _link("Анемона", "mnogoletnie-anemona"),
    _link("Гортензия крупнолистная", "mnogoletnie-gortenziya-krupnolistnaya"),
    _link("Ирисы", "mnogoletnie-irisy"),
    _link("Клематис", "mnogoletnie-klematis"),
    _link("Обриета", "mnogoletnie-obrieta"),
    _link("Платикодон", "mnogoletnie-platikodon"),
    _link("Армерия", "mnogoletnie-armeriya"),
    _link("Гвоздика", "mnogoletnie-gvozdika"),
    _link("Кореопсис", "mnogoletnie-koreopsis"),
    _link("Люпин", "mnogoletnie-lyupin"),
    _link("Барвинок", "mnogoletnie-barvinok"),
    _link("Гайлардия", "mnogoletnie-gaylardiya"),
    _link("Штокроза", "mnogoletnie-shtokroza"),
    _link("Гелениум", "mnogoletnie-gelenium"),
    _link("Эхинацея", "mnogoletnie-ekhinatseya"),
    _link("Гравилат", "mnogoletnie-gravilat"),
    _link("Дельфиниум", "mnogoletnie-delfinium"),
    _link("Колокольчик", "mnogoletnie-kolokolchik"),
    _link("Купальница", "mnogoletnie-kupalnitsa"),
    _link("Ландыш майский", "mnogoletnie-landysh-mayskiy"),
    _link("Лапчатка", "mnogoletnie-lapchatka"),
    _link("Лилейник", "mnogoletnie-lileynik"),
    _link("Астильба", "mnogoletnie-astilba"),
    _link("Астра", "mnogoletnie-astra"),
    _link("Бадан", "mnogoletnie-badan"),
    _link("Вероника/Вероникаструм", "mnogoletnie-veronika-veronikastrum"),
    _link("Гейхера", "mnogoletnie-geykhera"),
    _link("Дербенник", "mnogoletnie-derbennik"),
    _link("Злаки", "mnogoletnie-zlaki"),
    _link("Монарда", "mnogoletnie-monarda"),
    _link("Нивянник", "mnogoletnie-nivyannik"),
    _link("Прочие", "mnogoletnie-prochie"),
    _link("Пряно-декоративные травы", "mnogoletnie-pryano-dekorativnye-travy"),
    _link("Седум", "mnogoletnie-sedum"),
    _link("Тысячелистник", "mnogoletnie-tysyachelistnik"),
    _link("Флокс", "mnogoletnie-floks"),
    _link("Хоста", "mnogoletnie-khosta"),
    _link("Хризантема", "mnogoletnie-khrizantema"),
]

# --- Овощная рассада ---
_OVOSHCHI_CHILDREN: list[dict[str, Any]] = [
    _link("Вся овощная рассада", "ovoshchnaya-rassada"),
    _link("Тыквы", "ovoshchi-tykvy"),
    _link("Баклажаны", "ovoshchi-baklazhany"),
    _link("Томаты", "ovoshchi-tomaty"),
    _link("Арбуз/Дыня", "ovoshchi-arbuz-dynya"),
    _link("Кабачки", "ovoshchi-kabachki"),
    _link("Огурцы", "ovoshchi-ogurtsy"),
    _link("Перцы", "ovoshchi-pertsy"),
]

# --- Плодовые ---
_PLODOVYE_CHILDREN: list[dict[str, Any]] = [
    _link("Все плодовые", "plodovye"),
    _link("Вишня", "plodovye-vishnya"),
    _link("Груша", "plodovye-grusha"),
    _link("Жимолость", "plodovye-zhimolost-1"),
    _link("Малина", "plodovye-malina"),
    _link("Облепиха", "plodovye-oblepikha"),
    _link("Слива/СВГ", "plodovye-sliva-svg"),
    _link("Смородина", "plodovye-smorodina"),
    _link("Яблоня", "plodovye-yablonya"),
]

# --- Розы ---
_ROZY_CHILDREN: list[dict[str, Any]] = [
    _link("Все розы", "rozy"),
    _link("Английские", "rozy-angliyskie"),
    _link("Плетистые", "rozy-pletistye"),
    _link("Спрей", "rozy-sprey"),
    _link("Флорибунда", "rozy-floribunda"),
    _link("Чайно-гибридные", "rozy-chayno-gibridnye"),
    _link("Шрабы", "rozy-shraby"),
]

# --- Семена газонных трав ---
_SEMENA_CHILDREN: list[dict[str, Any]] = [
    _link("Все семена газонных трав", "semena-gazonnyh-trav"),
    _link("Газонная травосмесь Гринкипер", "semena-gazonnaya-travosmes-grinkiper"),
    _link("Газонная травосмесь Зеленый ковер/Канада", "semena-gazonnaya-travosmes-zelenyy-kover-kanada"),
]

# --- Хвойные: только роды/группы, без карточек «ель сибирская», «туя западная» и т.п. ---
_KHOYNYE_CHILDREN: list[dict[str, Any]] = [
    _link("Все хвойные", "hvoynye-derevya"),
    _link("Лиственница", "hvoynye-listvennitsa"),
    _link("Ель колючая", "hvoynye-el-kolyuchaya"),
    _link("Можжевельник", "hvoynye-mozhzhevelnik"),
    _link("Пихта", "hvoynye-pikhta"),
    _link("Сосна", "hvoynye-sosna"),
    _link("Туя", "hvoynye-tuya"),
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
    ap = ctx.get("active_plant")
    if isinstance(ap, dict) and (ap.get("category_slug") or "").strip():
        return str(ap.get("category_slug") or "").strip()
    if not active_plant_slug:
        return ""
    for p in ctx.get("plants") or []:
        if p.get("slug") == active_plant_slug or active_plant_slug in (p.get("merged_member_slugs") or []):
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

    from pages.catalog_subcategories import subcategory_slugs_for_nav_section

    for sec in sections:
        need_cats = _SECTION_EXPAND_CATEGORIES.get(sec["label"])
        if not need_cats or not sec.get("children"):
            continue
        sub_slugs = subcategory_slugs_for_nav_section(sec["label"])
        if active_cat in need_cats or active_cat in sub_slugs:
            sec["nav_expanded"] = True
            sec["nav_parent_active"] = True

    out = dict(ctx)
    out["catalog_nav_sections"] = sections
    out["catalog_nav_active_slug"] = active
    return out

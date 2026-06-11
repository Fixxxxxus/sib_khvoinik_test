"""
Навигация каталога — структура бокового меню как на old.gazony.ru.
В левой панели только уровень вида/класса (роды, группы), без сортов и торговых карточек.
Подсветка и раскрытие: по active_plant_slug / active_category_slug и по категории товара.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings


def _link(label: str, catalog_slug: str) -> dict[str, Any]:
    return {"label": label, "catalog_slug": catalog_slug}


# --- Кустарники ---
_KUSTARNIKI_CHILDREN: list[dict[str, Any]] = [
    _link("Все кустарники", "listvennye-kustarniki"),
    _link("Барбарис", "kustarniki-barbaris"),
    _link("Бересклет", "kustarniki-beresklet"),
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
    _link("Алиссиум", "odnoletnie-alissium"),
    _link("Ампельные", "odnoletnie-ampelnye"),
    _link("Бархатцы", "odnoletnie-barkhattsy"),
    _link("Вербена", "odnoletnie-verbena"),
    _link("Виола", "odnoletnie-viola"),
    _link("Гацания", "odnoletnie-gatsaniya"),
    _link("Георгина", "odnoletnie-georgina"),
    _link("Гипоэстес", "odnoletnie-gipoestes"),
    _link("Колеус", "odnoletnie-koleus"),
    _link("Кохия", "odnoletnie-kokhiya"),
    _link("Лобелия", "odnoletnie-lobeliya"),
    _link("Львиный зев (Антирринум)", "odnoletnie-lvinnyy-zev-antirrinum"),
    _link("Петуния", "odnoletnie-petuniya"),
    _link("Сальвия", "odnoletnie-salviya"),
    _link("Цинерария", "odnoletnie-tsinerariya"),
]

# --- Деревья ---
_DEREVYA_CHILDREN: list[dict[str, Any]] = [
    _link("Все деревья", "derevya"),
    _link("Вяз", "derevya-vyaz"),
    _link("Дуб", "derevya-dub"),
    _link("Клён", "derevya-klyen"),
    _link("Рябина", "derevya-ryabina"),
    _link("Черёмуха", "derevya-cheryemukha"),
    _link("Яблоня декоративная", "derevya-yablonya-dekorativnaya"),
]

# --- Многолетние цветы (два блока списка со скринов, объединены) ---
_MNOGOLETNIE_CHILDREN: list[dict[str, Any]] = [
    _link("Все многолетние цветы", "mnogoletnie-tsvety"),
    _link("Аквилегия", "mnogoletnie-akvilegiya"),
    _link("Анемона", "mnogoletnie-anemona"),
    _link("Армерия", "mnogoletnie-armeriya"),
    _link("Астильба", "mnogoletnie-astilba"),
    _link("Астра", "mnogoletnie-astra"),
    _link("Бадан", "mnogoletnie-badan"),
    _link("Барвинок", "mnogoletnie-barvinok"),
    _link("Бруннера", "mnogoletnie-brunnera"),
    _link("Вероника/Вероникаструм", "mnogoletnie-veronika-veronikastrum"),
    _link("Гайлардия", "mnogoletnie-gaylardiya"),
    _link("Гвоздика", "mnogoletnie-gvozdika"),
    _link("Гейхера", "mnogoletnie-geykhera"),
    _link("Гелениум", "mnogoletnie-gelenium"),
    _link("Герань", "mnogoletnie-geran"),
    _link("Гортензия крупнолистная", "mnogoletnie-gortenziya-krupnolistnaya"),
    _link("Гравилат", "mnogoletnie-gravilat"),
    _link("Дельфиниум", "mnogoletnie-delfinium"),
    _link("Дербенник", "mnogoletnie-derbennik"),
    _link("Злаки", "mnogoletnie-zlaki"),
    _link("Ирисы", "mnogoletnie-irisy"),
    _link("Клематис", "mnogoletnie-klematis"),
    _link("Колокольчик", "mnogoletnie-kolokolchik"),
    _link("Кореопсис", "mnogoletnie-koreopsis"),
    _link("Купальница", "mnogoletnie-kupalnitsa"),
    _link("Ландыш майский", "mnogoletnie-landysh-mayskiy"),
    _link("Лапчатка", "mnogoletnie-lapchatka"),
    _link("Лилейник", "mnogoletnie-lileynik"),
    _link("Люпин", "mnogoletnie-lyupin"),
    _link("Монарда", "mnogoletnie-monarda"),
    _link("Нивянник", "mnogoletnie-nivyannik"),
    _link("Обриета", "mnogoletnie-obrieta"),
    _link("Пион", "mnogoletnie-pion"),
    _link("Платикодон", "mnogoletnie-platikodon"),
    _link("Прочие", "mnogoletnie-prochie"),
    _link("Пряно-декоративные травы", "mnogoletnie-pryano-dekorativnye-travy"),
    _link("Седум", "mnogoletnie-sedum"),
    _link("Тысячелистник", "mnogoletnie-tysyachelistnik"),
    _link("Флокс", "mnogoletnie-floks"),
    _link("Хоста", "mnogoletnie-khosta"),
    _link("Хризантема", "mnogoletnie-khrizantema"),
    _link("Штокроза", "mnogoletnie-shtokroza"),
    _link("Эхинацея", "mnogoletnie-ekhinatseya"),
]

# --- Овощная рассада ---
_OVOSHCHI_CHILDREN: list[dict[str, Any]] = [
    _link("Вся овощная рассада", "ovoshchnaya-rassada"),
    _link("Арбуз/Дыня", "ovoshchi-arbuz-dynya"),
    _link("Баклажаны", "ovoshchi-baklazhany"),
    _link("Кабачки", "ovoshchi-kabachki"),
    _link("Огурцы", "ovoshchi-ogurtsy"),
    _link("Перцы", "ovoshchi-pertsy"),
    _link("Томаты", "ovoshchi-tomaty"),
    _link("Тыквы", "ovoshchi-tykvy"),
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
    _link("Ель колючая", "hvoynye-el-kolyuchaya"),
    _link("Лиственница", "hvoynye-listvennitsa"),
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
    {"label": "Рулонные газоны", "icon": "layers", "named_url": "roll_lawn_price"},
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
            item["named_url_name"] = raw["named_url"]
        elif raw.get("catalog_slug"):
            item["href"] = reverse("catalog_item", kwargs={"slug": raw["catalog_slug"]})
            item["nav_slug"] = raw["catalog_slug"]
        return item

    sections: list[dict[str, Any]] = [resolve(s) for s in CATALOG_NAV_SECTIONS_RAW]

    def _collect_nav_slugs(sec_list: list[dict[str, Any]]) -> set[str]:
        out: set[str] = set()
        for sec in sec_list:
            ns = sec.get("nav_slug")
            if ns:
                out.add(str(ns))
            for m in sec.get("match_slugs") or []:
                out.add(str(m))
            for ch in sec.get("children") or []:
                cns = ch.get("nav_slug")
                if cns:
                    out.add(str(cns))
                for m in ch.get("match_slugs") or []:
                    out.add(str(m))
        return out

    # Один общий запрос подкатегорий на весь рендер вместо N запросов в цикле
    # по категориям: группируем по slug родителя и переиспользуем ниже.
    subs_all: list[Any] = []
    subs_by_parent: dict[str, list[Any]] = {}
    try:
        from django.apps import apps

        Sub = apps.get_model("pages", "CatalogSubcategory")
        # Сортировка parent_id, sort_order, label сохраняет прежний порядок
        # внутри каждого родителя (sort_order, label).
        subs_all = list(Sub.objects.select_related("parent").order_by("parent_id", "sort_order", "label"))
        for sub in subs_all:
            ps = str(sub.parent.slug or "").strip()
            if ps:
                subs_by_parent.setdefault(ps, []).append(sub)
    except Exception:  # pragma: no cover
        pass

    if getattr(settings, "USE_DATABASE_CATALOG", False):
        seen_slugs = _collect_nav_slugs(sections)
        extra: list[tuple[int, dict[str, Any]]] = []
        for cat in ctx.get("categories") or []:
            slug = str((cat or {}).get("slug") or "").strip()
            if not slug or slug in seen_slugs:
                continue
            label = str((cat or {}).get("label") or (cat or {}).get("card_label") or slug).strip()
            order = int((cat or {}).get("sort_order") or 0)
            subs = subs_by_parent.get(slug) or []
            if subs:
                children_raw: list[dict[str, Any]] = [_link(f"Все {label}", slug)]
                children_raw.extend(_link(s.label, str(s.slug)) for s in subs)
                raw: dict[str, Any] = {"label": label, "icon": "sprout", "children": children_raw}
            else:
                raw = {"label": label, "icon": "sprout", "catalog_slug": slug}
            item = resolve(raw)
            extra.append((order, item))
            seen_slugs.add(slug)
            if subs:
                for s in subs:
                    seen_slugs.add(str(s.slug))
        extra.sort(key=lambda x: x[0])
        for _, item in extra:
            sections.append(item)

    # Подкатегории берём из общего списка subs_all (запрос уже выполнен выше).
    for sub in subs_all:
        ps = str(sub.parent.slug or "").strip()
        sub_slug = str(sub.slug or "").strip()
        if not ps or not sub_slug:
            continue
        for sec in sections:
            ch = sec.get("children")
            if not ch:
                continue
            if not any(str(c.get("nav_slug") or "") == ps for c in ch):
                continue
            if any(str(c.get("nav_slug") or "") == sub_slug for c in ch):
                continue
            ch.append(
                {
                    "label": sub.label,
                    "href": reverse("catalog_item", kwargs={"slug": sub_slug}),
                    "nav_slug": sub_slug,
                }
            )

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
        nav_route = (ctx.get("active_catalog_nav_route") or "").strip()
        if nav_route and sec.get("named_url_name") == nav_route:
            return True
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

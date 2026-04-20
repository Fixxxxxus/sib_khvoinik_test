"""
Подразделы каталога: отдельный URL /catalog/<slug>/ и фильтр товаров по сегменту пути
на старом сайте (legacy_paths), например /product/odnoletnie_tsvety/petuniya/...
"""
from __future__ import annotations

from typing import Any

SUBCATEGORIES: list[dict[str, Any]] = [
{"slug": "odnoletnie-ampelnye", "label": "Ампельные", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("ampelnye",)},
    {"slug": "odnoletnie-barkhattsy", "label": "Бархатцы", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("barkhattsy",)},
    {"slug": "odnoletnie-petuniya", "label": "Петуния", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("petuniya",)},
    {"slug": "odnoletnie-koleus", "label": "Колеус", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("koleus",)},
    {"slug": "odnoletnie-viola", "label": "Виола", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("viola",)},
    {"slug": "odnoletnie-lobeliya", "label": "Лобелия", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("lobeliya",)},
    {"slug": "odnoletnie-ageratum", "label": "Агератум", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("ageratum",)},
    {"slug": "odnoletnie-alissium", "label": "Алиссиум", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("alissium",)},
    {"slug": "odnoletnie-verbena", "label": "Вербена", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("verbena",)},
    {"slug": "odnoletnie-gatsaniya", "label": "Гацания", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("gatsaniya",)},
    {"slug": "odnoletnie-georgina", "label": "Георгина", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("georgina",)},
    {"slug": "odnoletnie-gipoestes", "label": "Гипоэстес", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("gipoestes",)},
    {"slug": "odnoletnie-kokhiya", "label": "Кохия", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("kokhiya",)},
    {"slug": "odnoletnie-lvinnyy-zev-antirrinum", "label": "Львиный зев (Антирринум)", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("lvinnyy_zev_antirrinum",)},
    {"slug": "odnoletnie-salviya", "label": "Сальвия", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("salviya",)},
    {"slug": "odnoletnie-tsinerariya", "label": "Цинерария", "parent_slug": "odnoletniaia-rassada", "legacy_part1": "odnoletnie_tsvety", "legacy_segments": ("tsinerariya",)},
    {"slug": "mnogoletnie-pryano-dekorativnye-travy", "label": "Пряно-декоративные травы", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("pryano_dekorativnye_travy",)},
    {"slug": "mnogoletnie-geykhera", "label": "Гейхера", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("geykhera",)},
    {"slug": "mnogoletnie-khrizantema", "label": "Хризантема", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("khrizantema",)},
    {"slug": "mnogoletnie-prochie", "label": "Прочие", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("prochie",)},
    {"slug": "mnogoletnie-zlaki", "label": "Злаки", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("zlaki",)},
    {"slug": "mnogoletnie-khosta", "label": "Хоста", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("khosta",)},
    {"slug": "mnogoletnie-astilba", "label": "Астильба", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("astilba",)},
    {"slug": "mnogoletnie-floks", "label": "Флокс", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("floks",)},
    {"slug": "mnogoletnie-veronika-veronikastrum", "label": "Вероника / Вероникаструм", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("veronika_veronikastrum",)},
    {"slug": "mnogoletnie-gortenziya-krupnolistnaya", "label": "Гортензия крупнолистная", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("gortenziya_krupnolistnaya",)},
    {"slug": "mnogoletnie-irisy", "label": "Ирисы", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("irisy",)},
    {"slug": "mnogoletnie-klematis", "label": "Клематис", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("klematis",)},
    {"slug": "mnogoletnie-pion", "label": "Пион", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("pion",)},
    {"slug": "mnogoletnie-astra", "label": "Астра", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("astra",)},
    {"slug": "mnogoletnie-ekhinatseya", "label": "Эхинацея", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("ekhinatseya",)},
    {"slug": "mnogoletnie-geran", "label": "Герань", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("geran",)},
    {"slug": "mnogoletnie-lileynik", "label": "Лилейник", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("lileynik",)},
    {"slug": "mnogoletnie-monarda", "label": "Монарда", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("monarda",)},
    {"slug": "mnogoletnie-tysyachelistnik", "label": "Тысячелистник", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("tysyachelistnik",)},
    {"slug": "mnogoletnie-derbennik", "label": "Дербенник", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("derbennik",)},
    {"slug": "mnogoletnie-sedum", "label": "Седум", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("sedum",)},
    {"slug": "mnogoletnie-anemona", "label": "Анемона", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("anemona",)},
    {"slug": "mnogoletnie-badan", "label": "Бадан", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("badan",)},
    {"slug": "mnogoletnie-delfinium", "label": "Дельфиниум", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("delfinium",)},
    {"slug": "mnogoletnie-gvozdika", "label": "Гвоздика", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("gvozdika",)},
    {"slug": "mnogoletnie-koreopsis", "label": "Кореопсис", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("koreopsis",)},
    {"slug": "mnogoletnie-lyupin", "label": "Люпин", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("lyupin",)},
    {"slug": "mnogoletnie-akvilegiya", "label": "Аквилегия", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("akvilegiya",)},
    {"slug": "mnogoletnie-armeriya", "label": "Армерия", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("armeriya",)},
    {"slug": "mnogoletnie-barvinok", "label": "Барвинок", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("barvinok",)},
    {"slug": "mnogoletnie-brunnera", "label": "Бруннера", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("brunnera",)},
    {"slug": "mnogoletnie-gelenium", "label": "Гелениум", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("gelenium",)},
    {"slug": "mnogoletnie-gravilat", "label": "Гравилат", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("gravilat",)},
    {"slug": "mnogoletnie-kolokolchik", "label": "Колокольчик", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("kolokolchik",)},
    {"slug": "mnogoletnie-kupalnitsa", "label": "Купальница", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("kupalnitsa",)},
    {"slug": "mnogoletnie-landysh-mayskiy", "label": "Ландыш майский", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("landysh_mayskiy",)},
    {"slug": "mnogoletnie-nivyannik", "label": "Нивянник", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("nivyannik",)},
    {"slug": "mnogoletnie-platikodon", "label": "Платикодон", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("platikodon",)},
    {"slug": "mnogoletnie-shtokroza", "label": "Штокроза", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("shtokroza",)},
    {"slug": "mnogoletnie-lapchatka", "label": "Лапчатка", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("lapchatka_1",)},
    {"slug": "mnogoletnie-obrieta", "label": "Обриета", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("obrieta",)},
    {"slug": "mnogoletnie-gaylardiya", "label": "Гайлардия", "parent_slug": "mnogoletnie-tsvety", "legacy_part1": "mnogoletnie_tsvety", "legacy_segments": ("gaylardiya",)},
    {"slug": "ovoshchi-tomaty", "label": "Томаты", "parent_slug": "ovoshchnaya-rassada", "legacy_part1": "ovoshchnaya_rassada", "legacy_segments": ("tomaty",)},
    {"slug": "ovoshchi-pertsy", "label": "Перцы", "parent_slug": "ovoshchnaya-rassada", "legacy_part1": "ovoshchnaya_rassada", "legacy_segments": ("pertsy",)},
    {"slug": "ovoshchi-arbuz-dynya", "label": "Арбуз / Дыня", "parent_slug": "ovoshchnaya-rassada", "legacy_part1": "ovoshchnaya_rassada", "legacy_segments": ("arbuz_dynya",)},
    {"slug": "ovoshchi-ogurtsy", "label": "Огурцы", "parent_slug": "ovoshchnaya-rassada", "legacy_part1": "ovoshchnaya_rassada", "legacy_segments": ("ogurtsy",)},
    {"slug": "ovoshchi-baklazhany", "label": "Баклажаны", "parent_slug": "ovoshchnaya-rassada", "legacy_part1": "ovoshchnaya_rassada", "legacy_segments": ("baklazhany",)},
    {"slug": "ovoshchi-kabachki", "label": "Кабачки", "parent_slug": "ovoshchnaya-rassada", "legacy_part1": "ovoshchnaya_rassada", "legacy_segments": ("kabachki",)},
    {"slug": "ovoshchi-tykvy", "label": "Тыквы", "parent_slug": "ovoshchnaya-rassada", "legacy_part1": "ovoshchnaya_rassada", "legacy_segments": ("tykvy",)},
    {"slug": "rozy-chayno-gibridnye", "label": "Чайно-гибридные", "parent_slug": "rozy", "legacy_part1": "rozy", "legacy_segments": ("chayno_gibridnye",)},
    {"slug": "rozy-sprey", "label": "Спрей", "parent_slug": "rozy", "legacy_part1": "rozy", "legacy_segments": ("sprey",)},
    {"slug": "rozy-angliyskie", "label": "Английские", "parent_slug": "rozy", "legacy_part1": "rozy", "legacy_segments": ("angliyskie",)},
    {"slug": "rozy-floribunda", "label": "Флорибунда", "parent_slug": "rozy", "legacy_part1": "rozy", "legacy_segments": ("floribunda",)},
    {"slug": "rozy-shraby", "label": "Шрабы", "parent_slug": "rozy", "legacy_part1": "rozy", "legacy_segments": ("shraby",)},
    {"slug": "rozy-pletistye", "label": "Плетистые", "parent_slug": "rozy", "legacy_part1": "rozy", "legacy_segments": ("pletistye",)},
    {"slug": "kustarniki-gortenziya", "label": "Гортензия", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("gortenziya",)},
    {"slug": "kustarniki-siren", "label": "Сирень", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("siren",)},
    {"slug": "kustarniki-spireya", "label": "Спирея", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("spireya",)},
    {"slug": "kustarniki-puzyreplodnik", "label": "Пузыреплодник", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("puzyreplodnik",)},
    {"slug": "kustarniki-chubushnik", "label": "Чубушник", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("chubushnik",)},
    {"slug": "kustarniki-lapchatka", "label": "Лапчатка", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("lapchatka", "lapchatka_1")},
    {"slug": "kustarniki-barbaris", "label": "Барбарис", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("barbaris",)},
    {"slug": "kustarniki-deren", "label": "Дерен", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("deren",)},
    {"slug": "kustarniki-roza-morshchinistaya", "label": "Роза морщинистая", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("roza_morshchinistaya",)},
    {"slug": "kustarniki-kizilnik", "label": "Кизильник", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("kizilnik",)},
    {"slug": "kustarniki-zhimolost", "label": "Жимолость", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("zhimolost",)},
    {"slug": "kustarniki-lokh", "label": "Лох", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("lokh",)},
    {"slug": "kustarniki-ryabinnik", "label": "Рябинник", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("ryabinnik",)},
    {"slug": "kustarniki-smorodina-alpiyskaya", "label": "Смородина альпийская", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("smorodina_alpiyskaya",)},
    {"slug": "kustarniki-snezhnoyagodnik", "label": "Снежноягодник", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("snezhnoyagodnik",)},
    {"slug": "kustarniki-beresklet", "label": "Бересклет", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("beresklet",)},
    {"slug": "kustarniki-biryuchina", "label": "Бирючина", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("biryuchina",)},
    {"slug": "kustarniki-kalina", "label": "Калина", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("kalina",)},
    {"slug": "kustarniki-mindal", "label": "Миндаль", "parent_slug": "listvennye-kustarniki", "legacy_part1": "kustarniki", "legacy_segments": ("mindal",)},
    {"slug": "derevya-yablonya-dekorativnaya", "label": "Яблоня декоративная", "parent_slug": "derevya", "legacy_part1": "derevya", "legacy_segments": ("yablonya_dekorativnaya",)},
    {"slug": "derevya-klyen", "label": "Клён", "parent_slug": "derevya", "legacy_part1": "derevya", "legacy_segments": ("klyen",)},
    {"slug": "derevya-cheryemukha", "label": "Черёмуха", "parent_slug": "derevya", "legacy_part1": "derevya", "legacy_segments": ("cheryemukha",)},
    {"slug": "derevya-dub", "label": "Дуб", "parent_slug": "derevya", "legacy_part1": "derevya", "legacy_segments": ("dub",)},
    {"slug": "derevya-ryabina", "label": "Рябина", "parent_slug": "derevya", "legacy_part1": "derevya", "legacy_segments": ("ryabina",)},
    {"slug": "derevya-vyaz", "label": "Вяз", "parent_slug": "derevya", "legacy_part1": "derevya", "legacy_segments": ("vyaz",)},
    {"slug": "hvoynye-mozhzhevelnik", "label": "Можжевельник", "parent_slug": "hvoynye-derevya", "legacy_part1": "khvoynye", "legacy_segments": ("mozhzhevelnik",)},
    {"slug": "hvoynye-tuya", "label": "Туя", "parent_slug": "hvoynye-derevya", "legacy_part1": "khvoynye", "legacy_segments": ("tuya",)},
    {"slug": "hvoynye-el-kolyuchaya", "label": "Ель колючая", "parent_slug": "hvoynye-derevya", "legacy_part1": "khvoynye", "legacy_segments": ("el_kolyuchaya",)},
    {"slug": "hvoynye-sosna", "label": "Сосна", "parent_slug": "hvoynye-derevya", "legacy_part1": "khvoynye", "legacy_segments": ("sosna",)},
    {"slug": "hvoynye-pikhta", "label": "Пихта", "parent_slug": "hvoynye-derevya", "legacy_part1": "khvoynye", "legacy_segments": ("pikhta",)},
    {"slug": "hvoynye-listvennitsa", "label": "Лиственница", "parent_slug": "hvoynye-derevya", "legacy_part1": "khvoynye", "legacy_segments": ("listvennitsa",)},
    {"slug": "plodovye-yablonya", "label": "Яблоня", "parent_slug": "plodovye", "legacy_part1": "plodovye", "legacy_segments": ("yablonya",)},
    {"slug": "plodovye-smorodina", "label": "Смородина", "parent_slug": "plodovye", "legacy_part1": "plodovye", "legacy_segments": ("smorodina",)},
    {"slug": "plodovye-grusha", "label": "Груша", "parent_slug": "plodovye", "legacy_part1": "plodovye", "legacy_segments": ("grusha",)},
    {"slug": "plodovye-sliva-svg", "label": "Слива / СВГ", "parent_slug": "plodovye", "legacy_part1": "plodovye", "legacy_segments": ("sliva_svg",)},
    {"slug": "plodovye-malina", "label": "Малина", "parent_slug": "plodovye", "legacy_part1": "plodovye", "legacy_segments": ("malina",)},
    {"slug": "plodovye-zhimolost-1", "label": "Жимолость", "parent_slug": "plodovye", "legacy_part1": "plodovye", "legacy_segments": ("zhimolost_1",)},
    {"slug": "plodovye-vishnya", "label": "Вишня", "parent_slug": "plodovye", "legacy_part1": "plodovye", "legacy_segments": ("vishnya",)},
    {"slug": "plodovye-oblepikha", "label": "Облепиха", "parent_slug": "plodovye", "legacy_part1": "plodovye", "legacy_segments": ("oblepikha",)},
    {"slug": "semena-gazonnaya-travosmes-grinkiper", "label": "Газонная травосмесь Гринкипер", "parent_slug": "semena-gazonnyh-trav", "legacy_part1": "semena_gazonnykh_trav", "legacy_segments": ("gazonnaya_travosmes_grinkiper",)},
    {"slug": "semena-gazonnaya-travosmes-zelenyy-kover-kanada", "label": "Газонная травосмесь Зелёный ковёр / Канада", "parent_slug": "semena-gazonnyh-trav", "legacy_part1": "semena_gazonnykh_trav", "legacy_segments": ("gazonnaya_travosmes_zelenyy_kover_kanada",)},
]

SUBCATEGORIES_BY_SLUG: dict[str, dict[str, Any]] = {d["slug"]: d for d in SUBCATEGORIES}

# Родительская категория товара → заголовок блока в боковом меню (для раскрытия и подсветки)
_PARENT_SLUG_TO_NAV_SECTION: dict[str, str] = {
    "odnoletniaia-rassada": "Однолетние цветы",
    "ovoshchnaya-rassada": "Овощная рассада",
    "mnogoletnie-tsvety": "Многолетние цветы",
    "listvennye-kustarniki": "Кустарники",
    "puzyreplodnik": "Кустарники",
    "derevya": "Деревья",
    "hvoynye-derevya": "Хвойные",
    "plodovye": "Плодовые",
    "rozy": "Розы",
    "semena-gazonnyh-trav": "Семена газонных трав",
}

def subcategory_slugs_for_nav_section(section_label: str) -> frozenset[str]:
    """Все URL подразделов, относящихся к блоку меню с данным заголовком."""
    out: set[str] = set()
    for row in SUBCATEGORIES:
        parent = row["parent_slug"]
        if _PARENT_SLUG_TO_NAV_SECTION.get(parent) == section_label:
            out.add(row["slug"])
    try:
        from django.apps import apps

        Sub = apps.get_model("pages", "CatalogSubcategory")
        for row in Sub.objects.select_related("parent").values("slug", "parent__slug"):
            parent = str(row["parent__slug"] or "")
            if _PARENT_SLUG_TO_NAV_SECTION.get(parent) == section_label:
                out.add(str(row["slug"]))
    except Exception:  # pragma: no cover
        pass
    return frozenset(out)


def all_subcategory_slugs() -> frozenset[str]:
    base = frozenset(SUBCATEGORIES_BY_SLUG.keys())
    try:
        from django.apps import apps

        Sub = apps.get_model("pages", "CatalogSubcategory")
        return base | frozenset(Sub.objects.values_list("slug", flat=True))
    except Exception:  # pragma: no cover
        return base

def plant_matches_subcategory(plant: dict[str, Any], slug: str) -> bool:
    rule = SUBCATEGORIES_BY_SLUG.get(slug)
    if not rule:
        return False
    if (plant.get("category_slug") or "") != rule["parent_slug"]:
        return False
    part1 = rule["legacy_part1"]
    paths = plant.get("legacy_paths") or []
    for seg in rule["legacy_segments"]:
        needle = f"/product/{part1}/{seg}/"
        for lp in paths:
            if needle in lp:
                return True
    return False

def _db_subcategory_label(slug: str) -> str | None:
    try:
        from django.apps import apps

        Sub = apps.get_model("pages", "CatalogSubcategory")
        row = Sub.objects.filter(slug=slug).values_list("label", flat=True).first()
        return str(row) if row else None
    except Exception:  # pragma: no cover
        return None


def category_label_for_slug(slug: str, categories: list[dict[str, Any]] | None) -> str | None:
    if categories:
        for c in categories:
            if c.get("slug") == slug:
                return str(c.get("label") or slug)
    rule = SUBCATEGORIES_BY_SLUG.get(slug)
    if rule:
        return str(rule.get("label") or slug)
    db_label = _db_subcategory_label(slug)
    if db_label:
        return db_label
    return None


def category_heading_for_slug(slug: str, categories: list[dict[str, Any]] | None) -> str:
    """Заголовок страницы каталога: для подраздела — «Раздел → Подраздел», для категории из data — как в categories[]."""
    if categories:
        for c in categories:
            if c.get("slug") == slug:
                return str(c.get("label") or slug)
    rule = SUBCATEGORIES_BY_SLUG.get(slug)
    if rule:
        parent = rule["parent_slug"]
        section = _PARENT_SLUG_TO_NAV_SECTION.get(parent)
        if not section and categories:
            for c in categories:
                if c.get("slug") == parent:
                    section = str(c.get("card_label") or c.get("label") or parent)
                    break
        section = section or parent
        sub = str(rule.get("label") or slug)
        return f"{section} → {sub}"
    try:
        from django.apps import apps

        Sub = apps.get_model("pages", "CatalogSubcategory")
        row = Sub.objects.filter(slug=slug).select_related("parent").first()
        if row:
            parent = str(row.parent.slug)
            section = _PARENT_SLUG_TO_NAV_SECTION.get(parent)
            if not section and categories:
                for c in categories:
                    if c.get("slug") == parent:
                        section = str(c.get("card_label") or c.get("label") or parent)
                        break
            section = section or str(row.parent.label or parent)
            sub = str(row.label or slug)
            return f"{section} → {sub}"
    except Exception:  # pragma: no cover
        pass
    return str(slug)

def all_catalog_category_slugs(categories: list[dict[str, Any]]) -> frozenset[str]:
    base = frozenset(str(c["slug"]) for c in categories if c.get("slug"))
    return base | all_subcategory_slugs()

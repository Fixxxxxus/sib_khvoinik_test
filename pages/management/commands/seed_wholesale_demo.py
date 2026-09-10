"""Демо-наполнение скрытого оптового каталога /opt/.

ВАЖНО: всё, что создаётся ниже - ЗАГЛУШКА каркаса. Названия, размеры, наличие и
особенно ЦЕНЫ выдуманы и не являются офертой. Реальный список позиций текущего
плана продаж, оптовые цены и фотографии заказчик передаёт следующим слоем.

Команда запускается руками только в разработке:

    python manage.py seed_wholesale_demo
    python manage.py seed_wholesale_demo --remove

На проде её не запускают: каталог наполняется реальными позициями через админку.
Каждая запись помечена is_demo=True, в админке видна колонка «Демо», на витрине
у карточки стоит бейдж «демо».
"""

from django.core.management.base import BaseCommand

from pages.models import WholesaleItem, WholesaleItemVariant, WholesaleSection


DEMO_SECTIONS = [
    {
        "slug": "derevya",
        "title": "Деревья",
        "intro": "Крупномеры и саженцы из плана продаж. Отгрузка партиями, самовывоз или доставка.",
        "sort_order": 10,
        "items": [
            {
                "slug": "demo-lipa-melkolistnaya",
                "title": "Липа мелколистная",
                "size": "высота 3,0-3,5 м, ком 60 см",
                "price": "6500.00",
                "availability": "демо-остаток: 40 шт",
                "is_highlighted": True,
                "short_description": "Демо-позиция каркаса. Реальные размеры, остаток и цену подставит заказчик.",
                "variants": [
                    {"title": "Ком 60 см", "stock": 24, "sort_order": 10},
                    {"title": "Ком 80 см", "stock": 11, "price": "7900.00", "sort_order": 20},
                    {"title": "Контейнер C45", "stock": 0, "sort_order": 30},
                ],
            },
            {
                "slug": "demo-yablonya-dekorativnaya",
                "title": "Яблоня декоративная",
                "size": "высота 2,0-2,5 м, контейнер C20",
                "price": "4200.00",
                "availability": "демо-остаток: 65 шт",
                "short_description": "Демо-позиция каркаса. Реальные размеры, остаток и цену подставит заказчик.",
            },
        ],
    },
    {
        "slug": "kustarniki",
        "title": "Кустарники",
        "intro": "Кустарники для живых изгородей и массивов. Партии от 50 шт.",
        "sort_order": 20,
        "items": [
            {
                "slug": "demo-puzyreplodnik-kalinolistnyy",
                "title": "Пузыреплодник калинолистный",
                "size": "высота 60-80 см, контейнер C3",
                "price": "540.00",
                "availability": "демо-остаток: 800 шт",
                "is_highlighted": True,
                "short_description": "Демо-позиция каркаса. Реальные размеры, остаток и цену подставит заказчик.",
                "variants": [
                    {"title": "Высота 60-80 см", "stock": 930, "sort_order": 10},
                    {"title": "Высота 80-100 см", "stock": 386, "price": "690.00", "sort_order": 20},
                ],
            },
            {
                "slug": "demo-spireya-yaponskaya",
                "title": "Спирея японская",
                "size": "высота 30-40 см, контейнер C2",
                "price": "380.00",
                "availability": "демо-остаток: 1200 шт",
                "short_description": "Демо-позиция каркаса. Реальные размеры, остаток и цену подставит заказчик.",
            },
        ],
    },
    {
        "slug": "hvoynye",
        "title": "Хвойные",
        "intro": "Хвойные из питомника: ели, сосны, туи. Комовые и контейнерные.",
        "sort_order": 30,
        "items": [
            {
                "slug": "demo-el-obyknovennaya",
                "title": "Ель обыкновенная",
                "size": "высота 2,0-2,5 м, ком 50 см",
                "price": "5900.00",
                "availability": "демо-остаток: 120 шт",
                "short_description": "Демо-позиция каркаса. Реальные размеры, остаток и цену подставит заказчик.",
            },
            {
                "slug": "demo-tuya-zapadnaya-smaragd",
                "title": "Туя западная Смарагд",
                "size": "высота 1,2-1,4 м, контейнер C10",
                "price": "2450.00",
                "availability": "демо-остаток: 300 шт",
                "short_description": "Демо-позиция каркаса. Реальные размеры, остаток и цену подставит заказчик.",
            },
        ],
    },
]


def seed_demo():
    for order, block in enumerate(DEMO_SECTIONS):
        section, _ = WholesaleSection.objects.get_or_create(
            slug=block["slug"],
            defaults={
                "title": block["title"],
                "intro": block["intro"],
                "sort_order": block["sort_order"],
                "is_active": True,
                "is_demo": True,
            },
        )
        for item_order, item in enumerate(block["items"]):
            obj, _ = WholesaleItem.objects.get_or_create(
                section=section,
                slug=item["slug"],
                defaults={
                    "title": item["title"],
                    "size": item["size"],
                    "price": item["price"],
                    "unit": "шт",
                    "availability": item["availability"],
                    "short_description": item["short_description"],
                    "is_highlighted": item.get("is_highlighted", False),
                    "sort_order": (item_order + 1) * 10,
                    "is_active": True,
                    "is_demo": True,
                },
            )
            # Варианты есть не у всех демо-позиций: карточка без вариантов должна
            # работать как раньше, одним степпером.
            for variant_order, variant in enumerate(item.get("variants", [])):
                WholesaleItemVariant.objects.get_or_create(
                    item=obj,
                    title=variant["title"],
                    defaults={
                        "stock": variant["stock"],
                        "price": variant.get("price"),
                        "sort_order": variant.get("sort_order", (variant_order + 1) * 10),
                        "is_active": True,
                    },
                )


def unseed_demo():
    slugs = [item["slug"] for block in DEMO_SECTIONS for item in block["items"]]
    WholesaleItem.objects.filter(slug__in=slugs, is_demo=True).delete()
    WholesaleSection.objects.filter(
        slug__in=[block["slug"] for block in DEMO_SECTIONS], is_demo=True
    ).delete()


class Command(BaseCommand):
    help = "Наполняет оптовый каталог /opt/ демо-позициями (только для разработки)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Удалить демо-позиции вместо создания.",
        )

    def handle(self, *args, **options):
        if options["remove"]:
            unseed_demo()
            self.stdout.write(self.style.SUCCESS("Демо-позиции оптового каталога удалены."))
            return
        seed_demo()
        self.stdout.write(self.style.SUCCESS("Демо-позиции оптового каталога созданы."))

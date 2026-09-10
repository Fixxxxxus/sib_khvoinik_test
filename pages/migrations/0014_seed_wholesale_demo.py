"""Демо-наполнение скрытого оптового каталога /opt/.

ВАЖНО: всё, что создаётся ниже - ЗАГЛУШКА каркаса. Названия, размеры, наличие и
особенно ЦЕНЫ выдуманы и не являются офертой. Реальный список позиций текущего
плана продаж, оптовые цены и фотографии заказчик передаёт следующим слоем.

Каждая запись помечена is_demo=True: в админке видна колонка «Демо», на витрине
у карточки стоит бейдж «демо». Перед запуском рекламы демо-записи удаляют или
переводят в is_active=False.

Откат миграции удаляет ровно эти записи (по слагу и признаку is_demo), реальные
позиции не трогает.
"""

from django.db import migrations

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


def seed_demo(apps, schema_editor):
    Section = apps.get_model("pages", "WholesaleSection")
    Item = apps.get_model("pages", "WholesaleItem")
    for order, block in enumerate(DEMO_SECTIONS):
        section, _ = Section.objects.get_or_create(
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
            Item.objects.get_or_create(
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


def unseed_demo(apps, schema_editor):
    Section = apps.get_model("pages", "WholesaleSection")
    Item = apps.get_model("pages", "WholesaleItem")
    slugs = [item["slug"] for block in DEMO_SECTIONS for item in block["items"]]
    Item.objects.filter(slug__in=slugs, is_demo=True).delete()
    Section.objects.filter(
        slug__in=[block["slug"] for block in DEMO_SECTIONS], is_demo=True
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0013_wholesaleitem_wholesaleorder_wholesalesection_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_demo, unseed_demo),
    ]

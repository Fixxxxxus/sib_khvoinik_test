from __future__ import annotations

from django.db import migrations

HVOYNYE_FALLBACK = "media/images/pitomnik-product-hvoynye.jpg"
LISTV_FALLBACK = "media/images/pitomnik-product-listvennye.jpg"
MIG = "media/images/catalog/migrated/"

# (название, размер, цена, путь-к-фото-в-static, alt)
KIRZA = [
    ("Ель канадская «Эхиниформис»", "С5, H 20-25 см", 3900, MIG + "el-kanadskaya-picea-glauca-daisy-s-white-s7-5-h-40-60-b6348996.webp", "Ель канадская"),
    ("Ель колючая голубая «Блю Даймонд»", "ком+сетка, H 80-100 см", 14900, MIG + "el-kolyuchaya-golubaya-picea-pungens-s2-3-h-15-25.webp", "Ель колючая голубая Блю Даймонд"),
    ("Сосна горная «Мугус»", "ком+сетка, H 50-60 см", 10900, MIG + "sosna-gornaya-pinus-mugo-mughus.webp", "Сосна горная Мугус"),
    ("Сосна горная «Винтер Голд»", "ком+сетка, H 30-40 см", 9900, MIG + "sosna-gornaya-pinus-mugo-pumilio-s2-3-h-15-20.webp", "Сосна горная Винтер Голд"),
    ("Пихта сибирская", "ком+сетка, H 1,2-1,4 м", 9900, MIG + "pihta-shershavoplodnaya-abies-lasiocarpa-compacta.webp", "Пихта сибирская"),
    ("Пихта сибирская", "ком+сетка, H 1,0-1,2 м", 8900, MIG + "pihta-shershavoplodnaya-abies-lasiocarpa-compacta.webp", "Пихта сибирская"),
    ("Лиственница сибирская", "ком+сетка, H 1,6-1,8 м", 6000, MIG + "listvennitsa-evropeyskaya-larix-dec-dua.webp", "Лиственница сибирская"),
    ("Черёмуха «Красный шатёр»", "штамб, ком+сетка, H 3-3,5 м", 13900, MIG + "cheremuha-shuberta-prunus-virginiana-shubert-kom-setka-d-600-4de16322.webp", "Черёмуха Красный шатёр"),
    ("Черёмуха Шуберта", "ком+сетка, H 3,5-4 м", 20900, MIG + "cheremuha-shuberta-prunus-virginiana-shubert-kom-setka-d-600-4de16322.webp", "Черёмуха Шуберта"),
    ("Черёмуха Шуберта", "ком+сетка, H 2-2,5 м", 9000, MIG + "cheremuha-shuberta-prunus-virginiana-shubert-kom-setka-d-600-4de16322.webp", "Черёмуха Шуберта"),
    ("Рябина обыкновенная", "ком+сетка, H 2-2,5 м", 4900, MIG + "ryabina-obyknovennaya-sorbus-aucuparia-shtamb-kom-setka-d-600-h-300-350.webp", "Рябина обыкновенная"),
    ("Тополь пирамидальный", "ком+сетка, H 3-3,5 м", 13900, LISTV_FALLBACK, "Тополь пирамидальный"),
    ("Берёза повислая", "ком+сетка, H 2,5-3 м", 9500, LISTV_FALLBACK, "Берёза повислая"),
    ("Липа мелколистная", "ком+сетка, H 2,5-3 м", 15000, LISTV_FALLBACK, "Липа мелколистная"),
    ("Липа мелколистная", "ком+сетка, H 1,8-2,5 м", 5900, LISTV_FALLBACK, "Липа мелколистная"),
    ("Клён Гиннала (приречный)", "ком+сетка, H 2-2,5 м", 11000, MIG + "klen-tatarskiy-ginala-acer-tataricum-ginnala-h-200-250-kom-setka-d-600.webp", "Клён Гиннала"),
    ("Яблоня Маковецкого", "ком+сетка, H 2-2,5 м", 14500, MIG + "yablonya-dekorativnaya-makovetskogo-malus-makowieckiana-kom-setka-d-600-h-2-0-2-5.webp", "Яблоня Маковецкого"),
    ("Яблоня Недзвецкого", "ком+сетка, H 1,6-1,8 м", 6000, MIG + "yablonya-dekorativnaya-nedzvetskogo-malus-niedzwetzkyana-kom-setka-d-600-h-1-2-1-5.webp", "Яблоня Недзвецкого"),
]

PERM = [
    ("Берёза повислая", "ком+сетка, H 1,5-2 м", 4000, LISTV_FALLBACK, "Берёза повислая"),
    ("Берёза повислая", "ком+сетка, H 2-3 м", 8000, LISTV_FALLBACK, "Берёза повислая"),
    ("Ель обыкновенная", "ком+сетка, H 0,5-1 м", 4500, MIG + "el-obyknovennaya-picea-abies-kom-setka-h-1-0-1-2.webp", "Ель обыкновенная"),
    ("Ель обыкновенная", "ком+сетка, H 1-1,5 м", 5500, MIG + "el-obyknovennaya-picea-abies-kom-setka-h-1-0-1-2.webp", "Ель обыкновенная"),
    ("Ель обыкновенная", "ком+сетка, H 1,5-2 м", 9000, MIG + "el-obyknovennaya-picea-abies-kom-setka-h-2-5-3-0.webp", "Ель обыкновенная"),
    ("Ель обыкновенная", "ком+сетка, H 2-3 м", 12500, MIG + "el-obyknovennaya-picea-abies-kom-setka-h-2-5-3-0.webp", "Ель обыкновенная"),
    ("Ель обыкновенная", "ком+сетка, H 3-4 м", 22500, MIG + "el-obyknovennaya-picea-abies-kom-setka-h-3-0-3-5.webp", "Ель обыкновенная"),
    ("Ель обыкновенная", "ком+сетка, H 4-5 м", 46000, MIG + "el-obyknovennaya-picea-abies-kom-setka-h-3-0-3-5.webp", "Ель обыкновенная"),
    ("Сосна обыкновенная", "ком+сетка, H 0,5-1 м", 3000, MIG + "sosna-obyknovennaya-p-nus-sylv-stris-kom-setka-h-2-5-3-0.webp", "Сосна обыкновенная"),
    ("Сосна обыкновенная", "ком+сетка, H 1-1,5 м", 5000, MIG + "sosna-obyknovennaya-p-nus-sylv-stris-kom-setka-h-2-5-3-0.webp", "Сосна обыкновенная"),
    ("Сосна обыкновенная", "ком+сетка, H 1,5-2 м", 7000, MIG + "sosna-obyknovennaya-p-nus-sylv-stris-kom-setka-h-2-5-3-0.webp", "Сосна обыкновенная"),
]

INFO_ITEMS = [
    {"title": "Поставка осенью", "text": "Растения с комом и сеткой выкапываем и отгружаем в осеннюю посадку - в лучший срок для приживаемости."},
    {"title": "Бронь заранее", "text": "Закрепляем нужные позиции за вами до начала сезона, пока есть выбор размеров и форматов."},
    {"title": "Ограниченные объёмы", "text": "Крупномеры в наличии поштучно. На популярные позиции количество ограничено - кто раньше забронировал, тот и получил."},
    {"title": "Свой питомник и партнёры", "text": "Растения из питомников «Сибирских газонов» и проверенных питомников-партнёров."},
    {"title": "Подтверждение менеджером", "text": "После заявки менеджер свяжется, уточнит размеры, цену и сроки и подтвердит заказ."},
]


def seed(apps, schema_editor):
    PreorderGroup = apps.get_model("pages", "PreorderGroup")
    PreorderPlant = apps.get_model("pages", "PreorderPlant")
    PreorderSettings = apps.get_model("pages", "PreorderSettings")

    settings_obj, _ = PreorderSettings.objects.get_or_create(pk=1)
    if not settings_obj.info_json:
        settings_obj.info_json = INFO_ITEMS
        settings_obj.save()

    groups = [
        ("Наш питомник (Кирза)", "Новосибирск, собственный питомник и сортовая хвоя", 0, KIRZA),
        ("Питомник-партнёр (Пермь)", "Хвойные крупномеры от проверенного партнёра", 1, PERM),
    ]
    for label, note, order, items in groups:
        group, _ = PreorderGroup.objects.get_or_create(
            label=label, defaults={"note": note, "sort_order": order, "is_active": True}
        )
        # Засеваем позиции только если у группы их ещё нет (идемпотентность).
        if group.plants.exists():
            continue
        for idx, (name, size, price, img, alt) in enumerate(items):
            PreorderPlant.objects.create(
                group=group,
                name=name,
                size=size,
                price=price,
                image_path=img,
                image_alt=alt,
                sort_order=idx,
                is_active=True,
            )


def unseed(apps, schema_editor):
    PreorderPlant = apps.get_model("pages", "PreorderPlant")
    PreorderGroup = apps.get_model("pages", "PreorderGroup")
    PreorderPlant.objects.all().delete()
    PreorderGroup.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0007_preordergroup_preordersettings_preorderplant"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]

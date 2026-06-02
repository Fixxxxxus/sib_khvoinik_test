"""Нормализация длинного тире в контенте календаря ухода.

Длинное тире «—» (U+2014) запрещено в текстах, которые видит клиент: оно сидело
в темах и теле периодов (и на сайте в content_html, и в тизерах дайджеста). Меняем
на дефис «-». Источник (pages/calendar_data.py) уже поправлен, эта миграция чинит
уже засеянные строки на проде. Идемпотентна: повторный прогон ничего не находит.

En-dash «–» в диапазонах дат («25 апреля – 15 мая») НЕ трогаем - это не тот символ.
"""

from __future__ import annotations

from django.db import migrations

EM_DASH = "—"
HYPHEN = "-"
FIELDS = ("theme", "content_text", "content_html")


def normalize(apps, schema_editor):
    Period = apps.get_model("pages", "CareCalendarPeriod")
    to_update = []
    for period in Period.objects.all().iterator(chunk_size=500):
        changed = False
        for field in FIELDS:
            value = getattr(period, field) or ""
            if EM_DASH in value:
                setattr(period, field, value.replace(EM_DASH, HYPHEN))
                changed = True
        if changed:
            to_update.append(period)
    if to_update:
        Period.objects.bulk_update(to_update, list(FIELDS), batch_size=200)


def noop(apps, schema_editor):
    # Обратной операции нет: вернуть дефисы в тире нельзя без потери данных
    # (часть дефисов исходно была дефисами).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0005_care_calendar_period_upload_images"),
    ]

    operations = [
        migrations.RunPython(normalize, noop),
    ]

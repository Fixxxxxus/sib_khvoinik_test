from __future__ import annotations

from django.db import migrations, models

# Правки по задаче Б24 #1323 (маркетинг): заголовок про деревья без слова
# «Открыт», каталог без разделения на Кирза/Пермь, подача как «наличие».
NEW = {
    "hero_title": "Предзаказ деревьев на осень 2026",
    "hero_subtitle": "Забронируйте нужные деревья заранее. Количество ограничено.",
    "catalog_title": "Деревья в наличии",
    "catalog_subtitle": "Отметьте нужные позиции, они автоматически попадут в заявку.",
}

OLD = {
    "hero_title": "Открыт предзаказ растений на осень 2026",
    "hero_subtitle": "Забронируйте нужные растения заранее. Количество ограничено.",
    "catalog_title": "Доступные растения",
    "catalog_subtitle": "Отметьте нужные позиции — они автоматически попадут в заявку.",
}


def forwards(apps, schema_editor):
    PreorderSettings = apps.get_model("pages", "PreorderSettings")
    obj = PreorderSettings.objects.filter(pk=1).first()
    if not obj:
        return
    # Обновляем только если поле всё ещё со старым значением (не затираем правки из админки).
    changed = False
    for field, new_val in NEW.items():
        if getattr(obj, field) == OLD[field]:
            setattr(obj, field, new_val)
            changed = True
    if changed:
        obj.save()


def backwards(apps, schema_editor):
    PreorderSettings = apps.get_model("pages", "PreorderSettings")
    obj = PreorderSettings.objects.filter(pk=1).first()
    if not obj:
        return
    for field, old_val in OLD.items():
        if getattr(obj, field) == NEW[field]:
            setattr(obj, field, old_val)
    obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0008_seed_preorder"),
    ]

    operations = [
        migrations.AlterField(
            model_name="preordersettings",
            name="hero_title",
            field=models.CharField(
                default="Предзаказ деревьев на осень 2026", max_length=300, verbose_name="Заголовок (H1)"
            ),
        ),
        migrations.AlterField(
            model_name="preordersettings",
            name="hero_subtitle",
            field=models.CharField(
                default="Забронируйте нужные деревья заранее. Количество ограничено.",
                max_length=400,
                verbose_name="Подзаголовок",
            ),
        ),
        migrations.AlterField(
            model_name="preordersettings",
            name="catalog_title",
            field=models.CharField(
                default="Деревья в наличии", max_length=300, verbose_name="Заголовок каталога"
            ),
        ),
        migrations.AlterField(
            model_name="preordersettings",
            name="catalog_subtitle",
            field=models.CharField(
                blank=True,
                default="Отметьте нужные позиции, они автоматически попадут в заявку.",
                max_length=400,
                verbose_name="Подзаголовок каталога",
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.db import models
from django.db.models import Exists, OuterRef
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from pages.utils_slug import ascii_slugify, unique_slug_for_model


class CatalogCategory(models.Model):
    """Раздел каталога (деревья, кустарники, …)."""

    label = models.CharField(
        "Название раздела",
        max_length=200,
        help_text="Как на сайте в заголовке раздела. Например: «Хвойные деревья».",
    )
    slug = models.SlugField(
        "URL-метка (slug)",
        max_length=120,
        unique=True,
        help_text="Латиница в адресе: /catalog/&lt;slug&gt;/. Заполняется автоматически из названия, при необходимости отредактируйте.",
    )
    card_label = models.CharField(
        "Краткое имя на карточке",
        max_length=120,
        blank=True,
        help_text="Короткая подпись в сетке разделов. Если пусто — берётся полное название.",
    )
    description = models.TextField(
        "Краткое описание",
        blank=True,
        help_text="Подзаголовок на карточке раздела. Рекомендуется 30–160 символов, без перегруза техническими деталями.",
    )
    sort_order = models.PositiveIntegerField(
        "Порядок в списке",
        default=0,
        help_text="Меньше число — выше в списке категорий в админке и на сайте.",
    )
    hidden = models.BooleanField(
        "Скрыть с сайта",
        default=False,
        help_text="Раздел пропадает из меню каталога (например, сезонная рассада вне сезона). "
        "Прямые ссылки на раздел и его товары продолжают работать.",
    )
    cover_path = models.CharField(
        "Путь к обложке (файл в static)",
        max_length=500,
        blank=True,
        help_text="Относительно папки static/, например: media/images/pitomnik-product-hvoynye.jpg. "
        "Предпочтительно WebP/JPEG, ширина не менее 1200 px для чёткости на ретина-экранах.",
    )
    image_alt = models.CharField("Описание для alt у обложки", max_length=255, blank=True)
    hub_links = models.JSONField(
        "Ссылки хаба",
        default=list,
        blank=True,
        help_text='JSON-массив вида [{"label": "…", "slug": "…"}] для разделов-«хабов». Обычно оставьте []',
    )
    legacy_paths = models.JSONField("Старые пути (редиректы)", default=list, blank=True)

    class Meta:
        ordering = ["sort_order", "label"]
        verbose_name = "категория каталога"
        verbose_name_plural = "категории каталога"

    def __str__(self) -> str:
        return self.label

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not (self.slug or "").strip():
            base = ascii_slugify(self.label) or "category"
            self.slug = unique_slug_for_model(
                CatalogCategory, base, instance_pk=self.pk, slug_field="slug"
            )
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        if self.hub_links is None:
            self.hub_links = []
        if not isinstance(self.hub_links, list):
            raise ValidationError({"hub_links": "Ожидается JSON-массив объектов с полями label и slug."})


class CatalogSubcategory(models.Model):
    """Подраздел внутри категории (/catalog/<slug>/), как «Агератум» внутри однолетней рассады."""

    parent = models.ForeignKey(
        CatalogCategory,
        verbose_name="Родительская категория",
        related_name="subcategories",
        on_delete=models.CASCADE,
    )
    label = models.CharField("Название подраздела", max_length=200)
    slug = models.SlugField(
        "URL-метка (slug)",
        max_length=120,
        unique=True,
        help_text="Уникально во всём каталоге (не должен совпадать с другим разделом или карточкой растения): /catalog/&lt;slug&gt;/.",
    )
    sort_order = models.PositiveIntegerField(
        "Порядок в списке",
        default=0,
        help_text="В боковом меню и в админке: меньше — выше.",
    )

    class Meta:
        ordering = ["sort_order", "label"]
        verbose_name = "подкатегория каталога"
        verbose_name_plural = "подкатегории каталога"

    def __str__(self) -> str:
        return f"{self.label} ({self.parent.label})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not (self.slug or "").strip():
            base = ascii_slugify(self.label) or "subcategory"
            self.slug = unique_slug_for_model(
                CatalogSubcategory, base, instance_pk=self.pk, slug_field="slug"
            )
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        sl = (self.slug or "").strip()
        if not sl:
            return
        if CatalogCategory.objects.filter(slug=sl).exists():
            raise ValidationError({"slug": "Этот slug уже занят категорией верхнего уровня."})
        if Plant.objects.filter(slug=sl).exists():
            raise ValidationError(
                {"slug": "Этот slug занят карточкой растения — в каталоге будет конфликт URL."}
            )
        parent_slug = ""
        if self.parent_id:
            parent_slug = (CatalogCategory.objects.filter(pk=self.parent_id).values_list("slug", flat=True).first() or "")
        if parent_slug and sl == parent_slug:
            raise ValidationError({"slug": "Подкатегория не может совпадать по slug с родительской категорией."})


class Plant(models.Model):
    """Карточка растения в каталоге."""

    name = models.CharField(
        "Полное название",
        max_length=500,
        help_text="Как на карточке товара: русское название и при необходимости латынь. "
        "Без лишних технических хвостов в конце — форматы задаются в блоке «Варианты».",
    )
    slug = models.SlugField(
        "URL-метка",
        max_length=200,
        unique=True,
        blank=True,
        help_text="Генерируется из названия. Латиница, дефисы. Можно скорректировать вручную.",
    )
    category = models.ForeignKey(
        CatalogCategory,
        verbose_name="Категория",
        related_name="plants",
        on_delete=models.PROTECT,
    )
    description = models.TextField(
        "Описание",
        validators=[MinLengthValidator(20), MaxLengthValidator(50_000)],
        help_text="Текст для страницы товара. Рекомендуется 200–4000 знаков: факты, уход, зимостойкость. "
        "Минимум 20 символов (техническое ограничение), максимум 50 000.",
    )
    cover_path = models.CharField(
        "Главное фото (путь в static)",
        max_length=500,
        blank=True,
        help_text="Если фото уже лежит в репозитории: путь относительно static/, напр. media/images/catalog/....webp. "
        "Формат: JPEG/WebP, соотношение сторон около 4:3 или 3:2, по длинной стороне 1400–2400 px.",
    )
    cover_upload = models.ImageField(
        "Загрузить главное фото",
        upload_to="catalog/covers/%Y/%m/",
        blank=True,
        null=True,
        help_text="Файл сохранится в MEDIA (URL вида /media/…). Формат: WebP или JPEG. "
        "Соотношение сторон около 4:3 или 3:2, по длинной стороне 1400–2400 px.",
    )
    image_alt = models.CharField(
        "Alt для главного фото",
        max_length=255,
        blank=True,
        help_text="Кратко опишите растение на фото — для доступности и SEO.",
    )
    height_hint = models.CharField(
        "Подпись «Высота» в карточке",
        max_length=200,
        blank=True,
        help_text="Например: «выберите формат ниже» или фиксированная высота, если без вариантов.",
    )
    frost = models.CharField("Морозостойкость", max_length=120, blank=True, help_text="Например: -35°C")
    light = models.CharField("Освещённость", max_length=120, blank=True, help_text="Например: солнце / полутень")
    catalog_teaser_override = models.CharField(
        "Тизер цены (вручную)",
        max_length=300,
        blank=True,
        help_text="Если пусто — сайт сам соберёт строку из вариантов и цен.",
    )
    is_new = models.BooleanField("Новинка", default=False, help_text="Для фильтра в админке и бейджа на сайте.")
    is_published = models.BooleanField(
        "Показывать на сайте",
        default=True,
        help_text="Снимите галочку, чтобы скрыть позицию без удаления.",
    )
    also_in_category_slugs = models.JSONField(
        "Дополнительные категории (slug)",
        default=list,
        blank=True,
        help_text='Список строк-slug, например ["kustarniki-gortenziya"]. Для подразделов каталога.',
    )
    legacy_paths = models.JSONField("Старые URL (редиректы)", default=list, blank=True)
    specs_json = models.JSONField(
        "Характеристики (JSON)",
        default=dict,
        blank=True,
        help_text="Плоский объект {\"Высота\": \"до 6 м\", \"Семейство\": \"…\"}. Дублирует удобство экспорта; "
        "в админке удобнее заполнять строки в блоке «Характеристики» ниже — они синхронизируются при сохранении.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "растение"
        verbose_name_plural = "растения"

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not (self.slug or "").strip():
            base = ascii_slugify(self.name) or "plant"
            self.slug = unique_slug_for_model(Plant, base, instance_pk=self.pk, slug_field="slug")
        super().save(*args, **kwargs)

    @classmethod
    def queryset_published(cls) -> models.QuerySet[Plant]:
        return cls.objects.filter(is_published=True).select_related("category")

    @classmethod
    def with_stock_annotation(cls, qs: models.QuerySet[Plant]) -> models.QuerySet[Plant]:
        v = PlantVariant.objects.filter(plant_id=OuterRef("pk"), in_stock=True)
        return qs.annotate(_has_stock=Exists(v))

    def clean(self) -> None:
        super().clean()
        if not (self.cover_path or "").strip() and not self.cover_upload:
            raise ValidationError(
                "Загрузите главное фото — иначе на сайте не будет изображения в карточке."
            )


class PlantVariant(models.Model):
    """Вариант формата (высота, контейнер, цена)."""

    plant = models.ForeignKey(Plant, verbose_name="Растение", related_name="variants", on_delete=models.CASCADE)
    height = models.CharField("Высота / размер", max_length=120, blank=True, help_text="Например: h 60-90")
    container = models.CharField(
        "Контейнер / формат",
        max_length=200,
        blank=True,
        help_text="Например: С3, Р9, Ком+Сетка",
    )
    price = models.CharField(
        "Цена",
        max_length=80,
        blank=True,
        help_text="Как на сайте, с «₽», напр. «1 590 ₽» или «от 18 000 ₽».",
    )
    in_stock = models.BooleanField("В наличии", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "вариант (цена/формат)"
        verbose_name_plural = "варианты (цены/форматы)"

    def __str__(self) -> str:
        return f"{self.plant_id}: {self.height} {self.container} {self.price}"


class PlantGalleryImage(models.Model):
    """Дополнительные фото в карточке."""

    plant = models.ForeignKey(Plant, verbose_name="Растение", related_name="gallery_images", on_delete=models.CASCADE)
    image = models.ImageField("Файл", upload_to="catalog/gallery/%Y/%m/")
    alt_text = models.CharField("Подпись (alt)", max_length=255, blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "фото галереи"
        verbose_name_plural = "галерея изображений"

    def __str__(self) -> str:
        return f"Фото #{self.sort_order} — {self.plant}"


class PlantCharacteristic(models.Model):
    """Строка характеристик (удобнее, чем сырой JSON)."""

    plant = models.ForeignKey(Plant, verbose_name="Растение", related_name="characteristics", on_delete=models.CASCADE)
    label = models.CharField("Название", max_length=120, help_text="Например: «Зимостойкость», «Скорость роста».")
    value = models.CharField("Значение", max_length=500)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "характеристика"
        verbose_name_plural = "характеристики (таблица)"

    def __str__(self) -> str:
        return f"{self.label}: {self.value}"


def plant_specs_as_rows(plant: Plant) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for ch in plant.characteristics.order_by("sort_order", "pk"):
        if ch.label.strip():
            rows.append({"label": ch.label.strip(), "value": (ch.value or "").strip()})
    if not rows and isinstance(plant.specs_json, dict):
        for k, v in plant.specs_json.items():
            rows.append({"label": str(k), "value": str(v)})
    return rows


def plant_specs_as_kv_json(plant: Plant) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in plant_specs_as_rows(plant):
        out[row["label"]] = row["value"]
    return out


def refresh_plant_specs_json(plant_id: int) -> None:
    if not Plant.objects.filter(pk=plant_id).exists():
        return
    rows = list(
        PlantCharacteristic.objects.filter(plant_id=plant_id)
        .order_by("sort_order", "pk")
        .values("label", "value")
    )
    data = {r["label"]: (r["value"] or "").strip() for r in rows if (r.get("label") or "").strip()}
    Plant.objects.filter(pk=plant_id).update(specs_json=data)


@receiver(post_save, sender=PlantCharacteristic)
@receiver(post_delete, sender=PlantCharacteristic)
def _on_plant_characteristic_changed(sender, instance: PlantCharacteristic, **kwargs: Any) -> None:
    if instance.plant_id:
        refresh_plant_specs_json(instance.plant_id)


# --- Календарь ухода (страница «Статьи» / sluzhba-zaboty/calendar/) — отдельно от каталога товаров ---


class CareCalendarCategory(models.Model):
    """Категория в календаре ухода (деревья, кустарники, …)."""

    label = models.CharField("Название", max_length=200)
    slug = models.SlugField("Slug (URL)", max_length=120, unique=True)
    sort_order = models.PositiveIntegerField("Порядок в списке", default=0)

    class Meta:
        ordering = ["sort_order", "label"]
        verbose_name = "календарь: категория растений"
        verbose_name_plural = "календарь: категории растений"

    def __str__(self) -> str:
        return self.label

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not (self.slug or "").strip():
            base = ascii_slugify(self.label) or "calendar-category"
            self.slug = unique_slug_for_model(
                CareCalendarCategory, base, instance_pk=self.pk, slug_field="slug"
            )
        super().save(*args, **kwargs)


class CareCalendarPlant(models.Model):
    """Карточка растения в календаре сезонных работ."""

    name = models.CharField("Название (рус.)", max_length=500)
    latin = models.CharField("Название (лат.)", max_length=500, blank=True)
    slug = models.SlugField("Slug (URL)", max_length=200, unique=True, blank=True)
    varieties_json = models.JSONField(
        "Сорта / формы (JSON-массив строк)",
        default=list,
        blank=True,
        help_text='Например: ["French Bolero", "Snow White"]. Пустой список [] — если не нужно.',
    )
    description = models.TextField(
        "Краткое описание",
        blank=True,
        help_text="Текст под заголовком на карточке (необязательно).",
    )
    primary_category = models.ForeignKey(
        CareCalendarCategory,
        verbose_name="Основная категория (для URL)",
        related_name="plants_by_primary",
        on_delete=models.PROTECT,
        help_text="Используется в адресе страницы: …/calendar/&lt;категория&gt;/&lt;растение&gt;/",
    )
    categories = models.ManyToManyField(
        CareCalendarCategory,
        verbose_name="Все категории",
        related_name="calendar_plants",
        blank=True,
        help_text="Отметьте одну или несколько. Основная категория добавится автоматически при сохранении.",
    )
    sort_order = models.PositiveIntegerField(
        "Порядок в списках",
        default=0,
        help_text="Меньше — выше внутри категории.",
    )
    is_published = models.BooleanField("Показывать на сайте", default=True)
    show_paid_service_cta = models.BooleanField(
        "Блок «Платная услуга» и форма выезда",
        default=False,
        help_text="Показывать на странице растения кнопку заказа выезда специалиста (модальное окно).",
    )
    yonote_id = models.CharField("ID Yonote (архив)", max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "календарь: растение"
        verbose_name_plural = "календарь: растения"

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not (self.slug or "").strip():
            base = ascii_slugify(self.name) or "calendar-plant"
            self.slug = unique_slug_for_model(
                CareCalendarPlant, base, instance_pk=self.pk, slug_field="slug"
            )
        super().save(*args, **kwargs)


class CareCalendarPlantGalleryImage(models.Model):
    """Галерея изображений карточки календаря (не привязана к конкретной дате)."""

    plant = models.ForeignKey(
        CareCalendarPlant,
        verbose_name="Растение",
        related_name="gallery_images",
        on_delete=models.CASCADE,
    )
    image = models.ImageField("Файл", upload_to="care_calendar/gallery/%Y/%m/")
    alt_text = models.CharField("Подпись (alt)", max_length=255, blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "календарь: фото галереи"
        verbose_name_plural = "календарь: галерея"

    def __str__(self) -> str:
        return f"Фото #{self.sort_order} — {self.plant}"


class CareCalendarSeasonRecommendation(models.Model):
    """Персональные рекомендации по уходу по сезону."""

    SEASON_SPRING = "spring"
    SEASON_SUMMER = "summer"
    SEASON_AUTUMN = "autumn"
    SEASON_WINTER = "winter"
    SEASON_CHOICES = [
        (SEASON_SPRING, "Весна"),
        (SEASON_SUMMER, "Лето"),
        (SEASON_AUTUMN, "Осень"),
        (SEASON_WINTER, "Зима"),
    ]

    plant = models.ForeignKey(
        CareCalendarPlant,
        verbose_name="Растение",
        related_name="season_recommendations",
        on_delete=models.CASCADE,
    )
    season = models.CharField("Сезон", max_length=16, choices=SEASON_CHOICES)
    body = models.TextField("Текст рекомендаций")
    sort_order = models.PositiveIntegerField("Порядок внутри сезона", default=0)

    class Meta:
        ordering = ["season", "sort_order", "pk"]
        verbose_name = "календарь: рекомендация по сезону"
        verbose_name_plural = "календарь: рекомендации по сезонам"

    def __str__(self) -> str:
        return f"{self.get_season_display()} — {self.plant}"


class CareCalendarPeriod(models.Model):
    """Одна точка графика ухода (дата + материалы)."""

    plant = models.ForeignKey(
        CareCalendarPlant,
        verbose_name="Растение",
        related_name="periods",
        on_delete=models.CASCADE,
    )
    sort_order = models.PositiveIntegerField("Порядок в графике", default=0)
    date_label = models.CharField(
        "Дата / период (подпись)",
        max_length=240,
        help_text="Как на сайте: «20 апреля», «15 – 25 мая» и т.п.",
    )
    theme = models.CharField("Тема работ", max_length=300, blank=True)
    content_text = models.TextField("Текст (plain)", blank=True)
    content_html = models.TextField("HTML (если заполнен — приоритетнее текста)", blank=True)
    period_image_1 = models.ImageField(
        "Фото 1 (файл)",
        upload_to="care_calendar/periods/%Y/%m/",
        blank=True,
        null=True,
    )
    period_image_2 = models.ImageField(
        "Фото 2 (файл)",
        upload_to="care_calendar/periods/%Y/%m/",
        blank=True,
        null=True,
    )
    period_image_3 = models.ImageField(
        "Фото 3 (файл)",
        upload_to="care_calendar/periods/%Y/%m/",
        blank=True,
        null=True,
    )
    period_image_4 = models.ImageField(
        "Фото 4 (файл)",
        upload_to="care_calendar/periods/%Y/%m/",
        blank=True,
        null=True,
    )
    period_image_5 = models.ImageField(
        "Фото 5 (файл)",
        upload_to="care_calendar/periods/%Y/%m/",
        blank=True,
        null=True,
    )
    period_image_6 = models.ImageField(
        "Фото 6 (файл)",
        upload_to="care_calendar/periods/%Y/%m/",
        blank=True,
        null=True,
    )
    images_json = models.JSONField(
        "Доп. ссылки на изображения (JSON-массив URL)",
        default=list,
        blank=True,
        help_text='Опционально: внешние URL, напр. ["https://…/a.jpg"]. На сайте показываются после загруженных файлов.',
    )
    products_json = models.JSONField(
        "Рекомендуемые препараты (JSON-массив строк)",
        default=list,
        blank=True,
    )
    videos_json = models.JSONField(
        'Видео (JSON-массив объектов {"label":"…","url":"…"})',
        default=list,
        blank=True,
    )

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "календарь: срок в графике"
        verbose_name_plural = "календарь: график ухода (сроки)"

    def __str__(self) -> str:
        return f"{self.date_label} — {self.plant}"


# ── Лендинг «Предзаказ растений на осень» (редактируется из админки) ──


class PreorderSettings(models.Model):
    """Тексты лендинга предзаказа. Синглтон: одна строка, правится из админки."""

    hero_eyebrow = models.CharField(
        "Плашка над заголовком",
        max_length=200,
        default="Осенняя посадка 2026",
    )
    hero_title = models.CharField(
        "Заголовок (H1)",
        max_length=300,
        default="Предзаказ деревьев на осень 2026",
    )
    hero_subtitle = models.CharField(
        "Подзаголовок",
        max_length=400,
        default="Забронируйте нужные деревья заранее. Количество ограничено.",
    )
    hero_cta = models.CharField("Кнопка в первом экране", max_length=80, default="Оставить заявку")

    info_title = models.CharField(
        "Заголовок информационного блока",
        max_length=300,
        default="Как работает предзаказ",
    )
    info_json = models.JSONField(
        "Пункты информационного блока (JSON-массив объектов {\"title\":\"…\",\"text\":\"…\"})",
        default=list,
        blank=True,
        help_text="Иконки подставляются автоматически по порядку.",
    )

    catalog_title = models.CharField(
        "Заголовок каталога",
        max_length=300,
        default="Деревья в наличии",
    )
    catalog_subtitle = models.CharField(
        "Подзаголовок каталога",
        max_length=400,
        blank=True,
        default="Отметьте нужные позиции, они автоматически попадут в заявку.",
    )

    form_title = models.CharField("Заголовок формы", max_length=200, default="Забронировать растения")
    form_subtitle = models.CharField(
        "Подзаголовок формы",
        max_length=400,
        blank=True,
        default="Менеджер свяжется для подтверждения заказа в течение рабочего дня.",
    )
    form_submit = models.CharField("Кнопка отправки", max_length=80, default="Забронировать растения")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "предзаказ: тексты лендинга"
        verbose_name_plural = "предзаказ: тексты лендинга"

    def __str__(self) -> str:
        return "Тексты лендинга предзаказа"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "PreorderSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PreorderGroup(models.Model):
    """Группа (вкладка) каталога предзаказа, напр. «Наш питомник (Кирза)»."""

    label = models.CharField("Название вкладки", max_length=200)
    note = models.CharField(
        "Подпись под вкладкой",
        max_length=300,
        blank=True,
        help_text="Короткое пояснение, напр. «Новосибирск, собственный питомник».",
    )
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Показывать", default=True)

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "предзаказ: группа (вкладка)"
        verbose_name_plural = "предзаказ: группы (вкладки)"

    def __str__(self) -> str:
        return self.label


class PreorderPlant(models.Model):
    """Позиция в каталоге предзаказа. Полностью правится из админки."""

    group = models.ForeignKey(
        PreorderGroup,
        verbose_name="Группа (вкладка)",
        related_name="plants",
        on_delete=models.PROTECT,
    )
    name = models.CharField("Название", max_length=300)
    size = models.CharField(
        "Размер / формат",
        max_length=200,
        blank=True,
        help_text="Напр.: «ком+сетка, H 1,5-2 м».",
    )
    price = models.PositiveIntegerField(
        "Цена, ₽",
        null=True,
        blank=True,
        help_text="Цена по предзаказу за штуку. Пусто — цена не показывается («по запросу»).",
    )
    image_path = models.CharField(
        "Фото (путь в static)",
        max_length=500,
        blank=True,
        help_text="Если фото уже в репозитории: путь относительно static/, "
        "напр. media/images/catalog/migrated/....webp",
    )
    image_upload = models.ImageField(
        "Загрузить фото",
        upload_to="preorder/%Y/%m/",
        blank=True,
        null=True,
        help_text="Файл сохранится в MEDIA. Имеет приоритет над «Фото (путь в static)».",
    )
    image_alt = models.CharField("Alt для фото", max_length=255, blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Показывать", default=True)

    class Meta:
        ordering = ["group__sort_order", "sort_order", "pk"]
        verbose_name = "предзаказ: растение"
        verbose_name_plural = "предзаказ: растения"

    def __str__(self) -> str:
        return self.name

    @property
    def image_url(self) -> str:
        """URL фото: загруженный файл имеет приоритет над путём в static."""
        if self.image_upload:
            try:
                return self.image_upload.url
            except ValueError:
                pass
        return ""

    @property
    def price_display(self) -> str:
        """'14900' -> '14 900 ₽' (пробел как разделитель тысяч)."""
        if not self.price:
            return ""
        return f"{self.price:,}".replace(",", " ") + " ₽"

    @property
    def choice_value(self) -> str:
        """Значение для чекбокса и заявки: «Название (размер)»."""
        return f"{self.name} ({self.size})" if self.size else self.name

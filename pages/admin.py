from __future__ import annotations

from io import BytesIO
from typing import Any

from django.contrib import admin, messages
from django.db.models import Q, QuerySet
from django.http import FileResponse, HttpRequest, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from pages.catalog_io import export_catalog_workbook, import_catalog_workbook
from pages.forms_catalog import PlantAdminForm
from pages.models import (
    CareCalendarCategory,
    CareCalendarPeriod,
    CareCalendarPlant,
    CareCalendarPlantGalleryImage,
    CareCalendarSeasonRecommendation,
    CatalogCategory,
    CatalogSubcategory,
    Plant,
    PlantGalleryImage,
    PlantVariant,
    PreorderGroup,
    PreorderPlant,
    PreorderSettings,
)
from django.templatetags.static import static as static_url


class CatalogSubcategoryInline(admin.TabularInline):
    model = CatalogSubcategory
    extra = 1
    fields = ("sort_order", "label", "slug")
    prepopulated_fields = {"slug": ("label",)}


class PlantVariantInline(admin.TabularInline):
    model = PlantVariant
    extra = 1
    fields = ("height", "container", "price", "in_stock")


class PlantGalleryImageInline(admin.TabularInline):
    model = PlantGalleryImage
    extra = 1
    fields = ("image", "preview")
    readonly_fields = ("preview",)

    @admin.display(description="Предпросмотр")
    def preview(self, obj: PlantGalleryImage) -> str:
        try:
            if obj.image:
                return format_html(
                    '<img src="{}" style="max-height:56px;border-radius:8px;object-fit:cover" alt="" />',
                    obj.image.url,
                )
        except ValueError:
            pass
        return "—"


class InStockFilter(admin.SimpleListFilter):
    title = "Наличие"
    parameter_name = "in_stock"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> list[tuple[str, str]]:
        return [
            ("yes", "Есть в наличии (хотя бы один вариант)"),
            ("no", "Нет в наличии / без вариантов"),
        ]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Plant]) -> QuerySet[Plant]:
        yes_pks = Plant.objects.filter(variants__in_stock=True).values_list("pk", flat=True).distinct()
        if self.value() == "yes":
            return queryset.filter(pk__in=yes_pks)
        if self.value() == "no":
            return queryset.exclude(pk__in=yes_pks)
        return queryset


@admin.register(CatalogCategory)
class CatalogCategoryAdmin(admin.ModelAdmin):
    inlines = (CatalogSubcategoryInline,)
    list_display = ("sort_order", "label", "slug", "hidden", "plant_count")
    list_display_links = ("label",)
    list_editable = ("sort_order", "hidden")
    list_filter = ("sort_order",)
    search_fields = ("label", "slug")
    ordering = ("sort_order", "label")
    prepopulated_fields = {"slug": ("label",)}

    fieldsets = (
        (
            None,
            {
                "fields": ("label", "slug", "sort_order", "hidden", "card_label"),
                "description": "Название и порядок видны на сайте. Slug можно поправить вручную, если автозаполнение не устроило. "
                "«Скрыть с сайта» убирает раздел из меню каталога, не удаляя его.",
            },
        ),
        (
            "Дополнительно",
            {
                "fields": ("hub_links", "legacy_paths"),
                "classes": ("collapse",),
                "description": "hub_links — JSON-массив ссылок для страниц-хабов. legacy_paths — старые URL для редиректов.",
            },
        ),
    )

    @admin.display(description="Растений")
    def plant_count(self, obj: CatalogCategory) -> int:
        return obj.plants.count()

    class Media:
        css = {"all": ("admin/css/catalog_admin.css",)}


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    form = PlantAdminForm
    change_form_template = "admin/pages/plant/change_form.html"
    save_on_top = True
    list_display = (
        "list_cover",
        "name",
        "category",
        "is_new",
        "is_published",
        "has_stock_display",
        "updated_at",
    )
    list_display_links = ("name",)
    list_filter = ("category", "is_new", "is_published", InStockFilter)
    search_fields = ("name", "description", "slug")
    ordering = ("category", "name")
    autocomplete_fields = ("category",)
    inlines = (PlantVariantInline, PlantGalleryImageInline)
    readonly_fields = ("cover_preview_block", "created_at", "updated_at")
    actions = ("export_workbook_action",)

    fieldsets = (
        (
            "Основное",
            {
                "fields": ("name", "slug", "category", "is_published", "is_new"),
                "description": "Slug создаётся автоматически при первом сохранении (латиница из названия). "
                "Поле можно отредактировать вручную. Категорию выберите из списка — она задаёт раздел на сайте.",
            },
        ),
        (
            "Подразделы каталога",
            {
                "fields": ("catalog_subcategory_slugs",),
                "description": "Сначала сохраните категорию, если подразделы не отображаются. Подкатегории из БД задаются в карточке категории (блок внизу).",
            },
        ),
        (
            "Описание",
            {
                "fields": ("description",),
                "description": "Рекомендуется 200–4000 символов: без «воды», структурируйте абзацами. "
                "Минимум 20 и максимум 50 000 символов (ограничение модели).",
            },
        ),
        (
            "Главное фото",
            {
                "fields": ("cover_upload", "cover_preview_block"),
                "description": "Изображение для карточки на сайте.",
            },
        ),
        (
            "JSON (редко нужно вручную)",
            {
                "fields": ("legacy_paths", "specs_json"),
                "classes": ("collapse", "sg-admin-tail"),
                "description": "Подразделы выбираются чекбоксами выше; сюда — только старые URL и сырой JSON характеристик.",
            },
        ),
        (
            "Служебное",
            {"fields": ("created_at", "updated_at"), "classes": ("sg-admin-tail",)},
        ),
    )

    class Media:
        css = {"all": ("admin/css/catalog_admin.css",)}

    def get_urls(self) -> list[Any]:
        urls = super().get_urls()
        custom = [
            path(
                "import-workbook/",
                self.admin_site.admin_view(self.import_workbook_view),
                name="pages_plant_import_workbook",
            ),
        ]
        return custom + urls

    def import_workbook_view(self, request: HttpRequest) -> Any:
        if request.method == "POST" and request.FILES.get("file"):
            raw = request.FILES["file"].read()
            try:
                stats = import_catalog_workbook(raw, dry_run=False)
            except Exception as exc:  # pragma: no cover
                messages.error(request, f"Ошибка импорта: {exc}")
            else:
                messages.success(
                    request,
                    f"Импорт выполнен: категорий {stats['categories']}, растений {stats['plants']}, вариантов {stats['variants']}.",
                )
            return HttpResponseRedirect(reverse("admin:pages_plant_changelist"))
        return TemplateResponse(
            request,
            "admin/pages/plant/import_workbook.html",
            {
                **self.admin_site.each_context(request),
                "title": "Импорт каталога из Excel",
                "opts": self.model._meta,
                "has_view_permission": True,
            },
        )

    @admin.display(description="Фото")
    def list_cover(self, obj: Plant) -> str:
        try:
            if obj.cover_upload:
                return format_html(
                    '<img src="{}" style="width:52px;height:52px;border-radius:10px;object-fit:cover" alt="" />',
                    obj.cover_upload.url,
                )
        except ValueError:
            pass
        p = (obj.cover_path or "").strip()
        if p:
            return format_html(
                '<img src="/static/{}" style="width:52px;height:52px;border-radius:10px;object-fit:cover" alt="" />',
                p,
            )
        return "—"

    @admin.display(description="Наличие", boolean=True)
    def has_stock_display(self, obj: Plant) -> bool:
        return obj.variants.filter(in_stock=True).exists()

    @admin.display(description="Предпросмотр главного фото")
    def cover_preview_block(self, obj: Plant) -> str:
        return self.list_cover(obj)

    @admin.action(description="Скачать полный каталог (Excel)")
    def export_workbook_action(self, request: HttpRequest, queryset: QuerySet[Plant]) -> FileResponse:
        data = export_catalog_workbook()
        return FileResponse(
            BytesIO(data),
            as_attachment=True,
            filename="catalog_export.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


class CareCalendarPlantGalleryImageInline(admin.TabularInline):
    model = CareCalendarPlantGalleryImage
    extra = 1
    fields = ("sort_order", "image", "alt_text", "preview")
    readonly_fields = ("preview",)

    @admin.display(description="Предпросмотр")
    def preview(self, obj: CareCalendarPlantGalleryImage) -> str:
        try:
            if obj.image:
                return format_html(
                    '<img src="{}" style="max-height:56px;border-radius:8px;object-fit:cover" alt="" />',
                    obj.image.url,
                )
        except ValueError:
            pass
        return "—"


class CareCalendarSeasonRecommendationInline(admin.TabularInline):
    model = CareCalendarSeasonRecommendation
    extra = 0
    fields = ("season", "sort_order", "body")


class CareCalendarPeriodInline(admin.StackedInline):
    model = CareCalendarPeriod
    extra = 0
    ordering = ("sort_order", "pk")
    fieldsets = (
        (
            None,
            {
                "fields": ("sort_order", "date_label", "theme"),
                "description": "Подпись даты — как на сайте в шкале сезона. Порядок задаёт последовательность карточек.",
            },
        ),
        (
            "Текст",
            {
                "fields": ("content_text", "content_html"),
                "description": "Если заполнен HTML, на сайте он главнее обычного текста.",
            },
        ),
        (
            "Фото к этому сроку",
            {
                "fields": (
                    "period_image_1",
                    "period_image_2",
                    "period_image_3",
                    "period_image_4",
                    "period_image_5",
                    "period_image_6",
                ),
                "description": "Загрузка файлов с компьютера (до 6 штук). На странице срока они показываются первыми, затем — картинки по ссылкам из JSON ниже.",
            },
        ),
        (
            "Медиа и списки (JSON)",
            {
                "fields": ("images_json", "products_json", "videos_json"),
                "description": "Дополнительные URL картинок; videos_json — массив объектов {\"label\":\"…\",\"url\":\"https://…\"}.",
            },
        ),
    )


class CareCalendarPrimaryCategoryFilter(admin.SimpleListFilter):
    title = "Основная категория"
    parameter_name = "primary_cat"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> list[tuple[str, str]]:
        return [(c.slug, c.label) for c in CareCalendarCategory.objects.order_by("sort_order", "label")]

    def queryset(self, request: HttpRequest, queryset: QuerySet[CareCalendarPlant]) -> QuerySet[CareCalendarPlant]:
        v = self.value()
        if v:
            return queryset.filter(primary_category__slug=v)
        return queryset


class CareCalendarExtraCategoryFilter(admin.SimpleListFilter):
    title = "Доп. категория (M2M)"
    parameter_name = "extra_cat"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> list[tuple[str, str]]:
        return [(c.slug, c.label) for c in CareCalendarCategory.objects.order_by("sort_order", "label")]

    def queryset(self, request: HttpRequest, queryset: QuerySet[CareCalendarPlant]) -> QuerySet[CareCalendarPlant]:
        v = self.value()
        if v:
            return queryset.filter(categories__slug=v).distinct()
        return queryset


@admin.register(CareCalendarCategory)
class CareCalendarCategoryAdmin(admin.ModelAdmin):
    list_display = ("sort_order", "label", "slug", "published_plant_count")
    list_display_links = ("label",)
    list_editable = ("sort_order",)
    search_fields = ("label", "slug")
    ordering = ("sort_order", "label")
    prepopulated_fields = {"slug": ("label",)}

    @admin.display(description="Растений (опубл.)")
    def published_plant_count(self, obj: CareCalendarCategory) -> int:
        return (
            CareCalendarPlant.objects.filter(is_published=True)
            .filter(Q(primary_category=obj) | Q(categories=obj))
            .distinct()
            .count()
        )


@admin.register(CareCalendarPlant)
class CareCalendarPlantAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = (
        "sort_order",
        "name",
        "latin_short",
        "primary_category",
        "is_published",
        "show_paid_service_cta",
        "period_count",
        "updated_at",
    )
    list_display_links = ("name",)
    list_editable = ("sort_order", "is_published", "show_paid_service_cta")
    list_filter = (
        CareCalendarPrimaryCategoryFilter,
        CareCalendarExtraCategoryFilter,
        "is_published",
        "show_paid_service_cta",
    )
    search_fields = ("name", "latin", "slug", "description")
    ordering = ("primary_category__sort_order", "sort_order", "name")
    filter_horizontal = ("categories",)
    autocomplete_fields = ("primary_category",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (
        CareCalendarPeriodInline,
        CareCalendarPlantGalleryImageInline,
        CareCalendarSeasonRecommendationInline,
    )
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "latin",
                    "slug",
                    "primary_category",
                    "categories",
                    "sort_order",
                    "is_published",
                    "show_paid_service_cta",
                ),
                "description": "Основная категория — часть URL. Дополнительные категории: растение покажется в нескольких разделах. "
                "После сохранения основная категория автоматически добавляется в «Все категории».",
            },
        ),
        (
            "Контент",
            {
                "fields": ("description", "varieties_json", "yonote_id"),
                "description": "Сорта — JSON-массив строк, например [\"Сорт А\", \"Сорт Б\"].",
            },
        ),
        (
            "Служебное",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Лат.")
    def latin_short(self, obj: CareCalendarPlant) -> str:
        t = (obj.latin or "").strip()
        return (t[:48] + "…") if len(t) > 48 else t

    @admin.display(description="Сроков в графике")
    def period_count(self, obj: CareCalendarPlant) -> int:
        return obj.periods.count()

    def save_related(self, request: HttpRequest, form: Any, formsets: Any, change: bool) -> None:
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if obj.pk and obj.primary_category_id:
            obj.categories.add(obj.primary_category_id)


@admin.register(PreorderSettings)
class PreorderSettingsAdmin(admin.ModelAdmin):
    save_on_top = True

    fieldsets = (
        ("Первый экран", {"fields": ("hero_eyebrow", "hero_title", "hero_subtitle", "hero_cta")}),
        ("Информационный блок", {"fields": ("info_title", "info_json")}),
        ("Каталог", {"fields": ("catalog_title", "catalog_subtitle")}),
        ("Форма заявки", {"fields": ("form_title", "form_subtitle", "form_submit")}),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Синглтон: не даём создавать вторую строку.
        return not PreorderSettings.objects.exists()

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(PreorderGroup)
class PreorderGroupAdmin(admin.ModelAdmin):
    list_display = ("sort_order", "label", "note", "is_active", "plant_count")
    list_display_links = ("label",)
    list_editable = ("sort_order", "is_active")

    @admin.display(description="Позиций")
    def plant_count(self, obj: PreorderGroup) -> int:
        return obj.plants.count()


@admin.register(PreorderPlant)
class PreorderPlantAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ("list_photo", "name", "group", "size", "price", "sort_order", "is_active")
    list_display_links = ("name",)
    list_editable = ("sort_order", "is_active")
    list_filter = ("group", "is_active")
    search_fields = ("name", "size")
    autocomplete_fields = ()
    readonly_fields = ("photo_preview",)

    fieldsets = (
        ("Основное", {"fields": ("group", "name", "size", "price", "is_active", "sort_order")}),
        (
            "Фото",
            {
                "fields": ("image_upload", "image_path", "image_alt", "photo_preview"),
                "description": "Загрузите файл или укажите путь в static. Загруженный файл имеет приоритет.",
            },
        ),
    )

    def _thumb(self, obj: PreorderPlant, h: int) -> str:
        url = obj.image_url
        if not url and obj.image_path:
            try:
                url = static_url(obj.image_path)
            except Exception:  # noqa: BLE001
                url = ""
        if url:
            return format_html(
                '<img src="{}" style="height:{}px;border-radius:8px;object-fit:cover" alt="" />', url, h
            )
        return "—"

    @admin.display(description="Фото")
    def list_photo(self, obj: PreorderPlant) -> str:
        return self._thumb(obj, 40)

    @admin.display(description="Предпросмотр")
    def photo_preview(self, obj: PreorderPlant) -> str:
        return self._thumb(obj, 160)


admin.site.site_header = "Сибирские газоны — администрирование"
admin.site.site_title = "Каталог и контент"
admin.site.index_title = "Панель управления"

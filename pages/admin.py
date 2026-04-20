from __future__ import annotations

from io import BytesIO
from typing import Any

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import FileResponse, HttpRequest, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin

from pages.catalog_io import export_catalog_workbook, import_catalog_workbook
from pages.models import CatalogCategory, Plant, PlantCharacteristic, PlantGalleryImage, PlantVariant
from pages.resources import CatalogCategoryResource, PlantResource


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


class PlantCharacteristicInline(admin.TabularInline):
    model = PlantCharacteristic
    extra = 1
    ordering = ("sort_order", "pk")


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
class CatalogCategoryAdmin(ImportExportModelAdmin):
    resource_classes = [CatalogCategoryResource]
    list_display = ("sort_order", "label", "slug", "cover_preview", "plant_count")
    list_display_links = ("label",)
    list_editable = ("sort_order",)
    list_filter = ("sort_order",)
    search_fields = ("label", "slug", "description")
    ordering = ("sort_order", "label")
    prepopulated_fields = {"slug": ("label",)}
    readonly_fields = ("cover_preview",)

    fieldsets = (
        (
            None,
            {
                "fields": ("label", "slug", "sort_order", "card_label", "description"),
                "description": "Название и порядок видны на сайте. Slug можно поправить вручную, если автозаполнение не устроило.",
            },
        ),
        (
            "Обложка раздела",
            {
                "fields": ("cover_path", "image_alt", "cover_preview"),
                "description": "Путь к файлу внутри папки static/ (как в репозитории). Рекомендуемый формат: WebP или JPEG, не меньше 1200 px по длинной стороне.",
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

    @admin.display(description="Обложка")
    def cover_preview(self, obj: CatalogCategory) -> str:
        p = (obj.cover_path or "").strip()
        if not p:
            return "—"
        return format_html(
            '<img src="/static/{}" style="max-height:48px;border-radius:8px;object-fit:cover" alt="" />',
            p,
        )

    @admin.display(description="Растений")
    def plant_count(self, obj: CatalogCategory) -> int:
        return obj.plants.count()


@admin.register(Plant)
class PlantAdmin(ImportExportModelAdmin):
    resource_classes = [PlantResource]
    change_list_template = "admin/pages/plant/change_list.html"
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
    inlines = (PlantVariantInline, PlantGalleryImageInline, PlantCharacteristicInline)
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
            "Краткие параметры (в карточке)",
            {
                "fields": ("height_hint", "frost", "light"),
                "description": "Подпись высоты, морозостойкость и свет — короткие строки.",
            },
        ),
        (
            "JSON (редко нужно вручную)",
            {
                "fields": ("also_in_category_slugs", "legacy_paths", "specs_json"),
                "classes": ("sg-admin-tail",),
                "description": "Дополнительные slug категорий и старые пути. specs_json синхронизируется с таблицей характеристик ниже.",
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

    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> Any:
        extra = extra_context or {}
        extra["import_workbook_url"] = reverse("admin:pages_plant_import_workbook")
        return super().changelist_view(request, extra_context=extra)

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


admin.site.site_header = "Сибирские газоны — администрирование"
admin.site.site_title = "Каталог и контент"
admin.site.index_title = "Панель управления"

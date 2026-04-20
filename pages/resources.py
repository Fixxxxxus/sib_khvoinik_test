"""Ресурсы django-import-export для CSV/XLSX в стандартной админке."""

from __future__ import annotations

from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from pages.models import CatalogCategory, Plant


class CatalogCategoryResource(resources.ModelResource):
    class Meta:
        model = CatalogCategory
        fields = (
            "slug",
            "label",
            "card_label",
            "description",
            "sort_order",
            "cover_path",
            "image_alt",
            "hub_links",
            "legacy_paths",
        )
        import_id_fields = ("slug",)


class PlantResource(resources.ModelResource):
    category_slug = fields.Field(
        column_name="category_slug",
        attribute="category",
        widget=ForeignKeyWidget(CatalogCategory, "slug"),
    )

    def dehydrate_category_slug(self, plant: Plant) -> str:
        return plant.category.slug if plant.category_id else ""

    class Meta:
        model = Plant
        fields = (
            "slug",
            "name",
            "category_slug",
            "description",
            "cover_path",
            "image_alt",
            "height_hint",
            "frost",
            "light",
            "catalog_teaser_override",
            "is_new",
            "is_published",
            "also_in_category_slugs",
            "legacy_paths",
        )
        import_id_fields = ("slug",)

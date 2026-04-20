"""Формы каталога для админки."""

from __future__ import annotations

from typing import Any

from django import forms

from pages.catalog_subcategories import SUBCATEGORIES
from pages.models import CatalogCategory, CatalogSubcategory, Plant


def static_subchoices_for_parent(parent_slug: str) -> list[tuple[str, str]]:
    return [(row["slug"], row["label"]) for row in SUBCATEGORIES if row["parent_slug"] == parent_slug]


def db_subchoices_for_parent(parent_slug: str) -> list[tuple[str, str]]:
    if not parent_slug:
        return []
    return list(
        CatalogSubcategory.objects.filter(parent__slug=parent_slug)
        .order_by("sort_order", "label")
        .values_list("slug", "label")
    )


def merged_subchoices_for_parent(parent_slug: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for slug, label in static_subchoices_for_parent(parent_slug):
        out.append((slug, label))
        seen.add(slug)
    for slug, label in db_subchoices_for_parent(parent_slug):
        if slug not in seen:
            out.append((slug, label))
            seen.add(slug)
    return out


class PlantAdminForm(forms.ModelForm):
    """Чекбоксы подразделов вместо ручного JSON also_in_category_slugs."""

    catalog_subcategory_slugs = forms.MultipleChoiceField(
        required=False,
        label="Подразделы каталога",
        widget=forms.CheckboxSelectMultiple,
        help_text="Подстраницы вида /catalog/…, где товар должен попадать в список (дополнительно к основной категории).",
    )

    class Meta:
        model = Plant
        fields = "__all__"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields.pop("also_in_category_slugs", None)
        parent_slug = self._resolve_category_slug()
        choices = merged_subchoices_for_parent(parent_slug)
        self.fields["catalog_subcategory_slugs"].choices = choices
        choice_slugs = {c[0] for c in choices}
        if self.instance.pk:
            also = list(self.instance.also_in_category_slugs or [])
            self.initial["catalog_subcategory_slugs"] = [x for x in also if x in choice_slugs]

    def _resolve_category_slug(self) -> str:
        cid = (self.data.get("category") or "").strip()
        if cid.isdigit():
            slug = CatalogCategory.objects.filter(pk=int(cid)).values_list("slug", flat=True).first()
            if slug:
                return str(slug)
        if self.instance.pk and self.instance.category_id:
            return str(self.instance.category.slug)
        return ""

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        cat = cleaned.get("category")
        parent = str(cat.slug) if cat else ""
        valid = {s for s, _ in merged_subchoices_for_parent(parent)}
        chosen = set(cleaned.get("catalog_subcategory_slugs") or [])
        cleaned["catalog_subcategory_slugs"] = sorted(chosen & valid)
        return cleaned

    def save(self, commit: bool = True) -> Plant:
        obj = super().save(commit=False)
        parent_slug = ""
        if obj.category_id:
            parent_slug = str(
                CatalogCategory.objects.filter(pk=obj.category_id).values_list("slug", flat=True).first() or ""
            )
        choices = merged_subchoices_for_parent(parent_slug)
        choice_slugs = {c[0] for c in choices}
        selected = list(self.cleaned_data.get("catalog_subcategory_slugs") or [])
        prev = list(obj.also_in_category_slugs or [])
        kept = [x for x in prev if x not in choice_slugs]
        obj.also_in_category_slugs = kept + selected
        if commit:
            obj.save()
            self.save_m2m()
        return obj

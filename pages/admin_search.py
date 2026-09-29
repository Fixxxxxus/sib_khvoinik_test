"""Поиск в админке без учёта регистра для кириллицы.

SQLite сравнивает LIKE без учёта регистра только для латиницы, поэтому штатный
поиск Django по «яблоня» не находил «Яблоня». Регистрируем в каждом соединении
функцию unicode_lower (Python str.lower) и ищем через неё.
"""

from __future__ import annotations

from typing import Any

from django.db import connection
from django.db.backends.signals import connection_created
from django.db.models import F, Func, Q, QuerySet

SQL_FUNCTION = "unicode_lower"


def _unicode_lower(value: Any) -> Any:
    return value.lower() if isinstance(value, str) else value


def _register(sender, connection, **kwargs) -> None:
    if connection.vendor == "sqlite":
        connection.connection.create_function(SQL_FUNCTION, 1, _unicode_lower, deterministic=True)


def register_unicode_lower() -> None:
    connection_created.connect(_register, dispatch_uid="pages_unicode_lower")


class UnicodeLower(Func):
    function = SQL_FUNCTION


def unicode_search(queryset: QuerySet, fields: tuple[str, ...], search_term: str) -> QuerySet:
    """Каждое слово запроса должно встретиться хотя бы в одном из полей.

    Поля с «__» (связанные модели) ищутся подзапросом, чтобы не плодить дубли строк.
    """
    words = search_term.split()
    if not words:
        return queryset
    model = queryset.model
    for word in words:
        needle = word.lower()
        condition = Q()
        for field in fields:
            if "__" in field:
                relation, _, rel_field = field.rpartition("__")
                related = model._meta.get_field(relation).related_model
                fk_name = model._meta.get_field(relation).field.name
                pks = (
                    related.objects.annotate(_needle=UnicodeLower(F(rel_field)))
                    .filter(_needle__contains=needle)
                    .values(fk_name)
                )
                condition |= Q(pk__in=pks)
            else:
                condition |= Q(pk__in=model.objects.annotate(_needle=UnicodeLower(F(field)))
                               .filter(_needle__contains=needle).values("pk"))
        queryset = queryset.filter(condition)
    return queryset


class UnicodeSearchMixin:
    """Подменяет поиск ModelAdmin на регистронезависимый (на SQLite)."""

    unicode_search_fields: tuple[str, ...] = ()

    def get_search_results(self, request, queryset, search_term):
        if connection.vendor != "sqlite" or not search_term.strip():
            return super().get_search_results(request, queryset, search_term)
        fields = self.unicode_search_fields or tuple(self.search_fields)
        return unicode_search(queryset, fields, search_term), False

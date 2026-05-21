"""Pytest конфиг проекта: подключает Django через pytest-django.

DJANGO_SETTINGS_MODULE задан в config/settings.py.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def pytest_configure(config):
    """Используем in-memory sqlite для тестов: быстро и без следов в db.sqlite3."""
    import django
    from django.conf import settings
    if not settings.configured:
        django.setup()

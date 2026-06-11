from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pages'

    def ready(self):
        # Сигналы инвалидации TTL-кэша каталога (pages/catalog_cache.py).
        from pages.catalog_cache import register_invalidation_signals

        register_invalidation_signals()

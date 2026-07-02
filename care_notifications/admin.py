from django.contrib import admin

from .models import CareSubscription, DigestDelivery, OneCCardSync, WeeklyPromo


@admin.register(CareSubscription)
class CareSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "email",
        "phone",
        "preferred_channel",
        "active",
        "source",
        "b24_lead_id",
        "b24_contact_id",
        "created_at",
    )
    list_filter = ("active", "preferred_channel", "source", "promo_subscribed")
    search_fields = ("name", "email", "phone", "token", "b24_lead_id", "b24_contact_id")
    readonly_fields = ("token", "created_at", "updated_at", "last_digest_sent_at", "unsubscribed_at")
    fieldsets = (
        ("Контакт", {"fields": ("name", "phone", "email")}),
        ("Подписка", {"fields": ("preferred_channel", "groups", "promo_subscribed", "active")}),
        ("Источник", {"fields": ("source", "page_path", "utm")}),
        ("Битрикс24", {"fields": ("b24_lead_id", "b24_contact_id")}),
        ("Мессенджеры", {"fields": ("telegram_chat_id", "telegram_opted_in_at", "max_chat_id", "max_opted_in_at")}),
        ("Служебное", {"fields": ("token", "created_at", "updated_at", "last_digest_sent_at", "unsubscribed_at")}),
    )


@admin.register(DigestDelivery)
class DigestDeliveryAdmin(admin.ModelAdmin):
    list_display = ("id", "subscription", "channel", "week_key", "status", "created_at")
    list_filter = ("status", "channel", "week_key")
    search_fields = ("subscription__email", "subscription__phone", "external_id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(OneCCardSync)
class OneCCardSyncAdmin(admin.ModelAdmin):
    list_display = ("id", "phone", "last_name", "first_name", "status", "attempts", "b24_contact_id", "created_at", "sent_at")
    list_filter = ("status",)
    search_fields = ("phone", "last_name", "first_name", "b24_contact_id")
    readonly_fields = ("created_at", "updated_at", "sent_at")


@admin.register(WeeklyPromo)
class WeeklyPromoAdmin(admin.ModelAdmin):
    list_display = ("week_key", "status", "has_image", "updated_at", "confirmed_at")
    list_filter = ("status",)
    search_fields = ("week_key", "text")
    readonly_fields = ("created_at", "updated_at", "confirmed_at")

    @admin.display(boolean=True, description="Картинка")
    def has_image(self, obj):
        return bool(obj.image)

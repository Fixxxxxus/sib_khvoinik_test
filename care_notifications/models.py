"""Модели подписки на дайджест Службы заботы.

Источник правды по статусу подписки и таксономии групп - Б24 (поле «Служба заботы»).
Локально храним: токен управляющей ссылки, контакты, последний канал, ссылку на Б24
и факты доставки для логирования.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models


CHANNEL_CHOICES = [
    ("email", "Email"),
    ("telegram", "Telegram"),
    ("max", "MAX"),
]

SOURCE_CHOICES = [
    ("purchase", "После покупки"),
    ("web", "С сайта"),
    ("ads", "С рекламы Службы заботы"),
    ("unknown", "Источник не определён"),
]


def _generate_token() -> str:
    """64 символа hex, влезает и в Telegram deep-link, и в MAX, и в URL."""
    raw = secrets.token_bytes(32)
    return raw.hex()


class CareSubscription(models.Model):
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=_generate_token,
        help_text="Подписывает ссылки /care/manage/?t=... и opt-in deep-links ботов.",
    )

    name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)

    preferred_channel = models.CharField(
        max_length=16,
        choices=CHANNEL_CHOICES,
        default="email",
    )

    groups = models.JSONField(
        default=list,
        help_text="slug'и групп из pages.data.CARE_SUBSCRIPTION_GROUPS, например ['seasonal','roses'].",
    )
    promo_subscribed = models.BooleanField(
        default=False,
        help_text="Согласие на новинки и акции (объединённая опция promo в форме).",
    )

    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="unknown")
    page_path = models.CharField(max_length=512, blank=True)
    utm = models.JSONField(default=dict, blank=True)

    b24_lead_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    b24_contact_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    active = models.BooleanField(default=True, db_index=True)

    telegram_chat_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    telegram_opted_in_at = models.DateTimeField(null=True, blank=True)
    max_chat_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    max_opted_in_at = models.DateTimeField(null=True, blank=True)

    last_digest_sent_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Подписка на Службу заботы"
        verbose_name_plural = "Подписки на Службу заботы"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        who = self.email or self.phone or "(anon)"
        return f"{who} · {self.preferred_channel} · {'on' if self.active else 'off'}"

    def signed_token(self) -> str:
        """HMAC-подпись токена общим SECRET_KEY: защита от перебора, если кто-то угадал uuid.

        Используется в URL `/care/manage/?t=<token>&s=<sig>`, чтобы атака на токены
        требовала ещё и совпадения подписи.
        """
        key = settings.SECRET_KEY.encode("utf-8")
        msg = self.token.encode("utf-8")
        return hmac.new(key, msg, hashlib.sha256).hexdigest()[:16]

    @classmethod
    def verify_signed_token(cls, token: str, signature: str) -> "CareSubscription | None":
        try:
            obj = cls.objects.get(token=token)
        except cls.DoesNotExist:
            return None
        if not hmac.compare_digest(obj.signed_token(), signature):
            return None
        return obj


class DigestDelivery(models.Model):
    """Лог доставки одного выпуска дайджеста одному подписчику в один канал.

    Нужен чтобы при перезапуске пайплайна не слать повторно, и для базовых метрик
    «сколько ушло сегодня».
    """

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_PENDING, "В очереди"),
        (STATUS_SENT, "Отправлено"),
        (STATUS_FAILED, "Ошибка"),
        (STATUS_SKIPPED, "Пропущено"),
    ]

    subscription = models.ForeignKey(
        CareSubscription,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES)
    week_key = models.CharField(
        max_length=16,
        help_text="ISO неделя выпуска, например 2026-W21. Идемпотентность дайджеста.",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.TextField(blank=True)
    external_id = models.CharField(
        max_length=128,
        blank=True,
        help_text="ID сообщения у провайдера (Unisender message_id, TG message_id и т.д.).",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Доставка дайджеста"
        verbose_name_plural = "Доставки дайджестов"
        unique_together = [("subscription", "channel", "week_key")]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.week_key} · {self.subscription_id} · {self.channel} · {self.status}"


class OneCCardSync(models.Model):
    """Журнал отправки цифровой карты в 1С:УНФ (best-effort + ретрай, задача #1231).

    На каждое оформление карты создаём строку - это и очередь на отправку, и аудит.
    Сразу пробуем отправить синхронно; при сбое запись остаётся pending, команда
    `sync_onec_cards` добивает её по крону. 1С делает upsert по телефону (телефон =
    идентификатор карты), поэтому повторная отправка дубля не плодит - ретраи безопасны.

    Источник для менеджеров - по-прежнему Б24; эта таблица только про доставку в 1С.
    """

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "В очереди"),
        (STATUS_SENT, "Отправлено"),
        (STATUS_FAILED, "Ошибка (исчерпаны попытки)"),
    ]

    phone = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Канонический +7XXXXXXXXXX - идентификатор карты в 1С.",
    )
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)

    b24_contact_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="ID контакта в Б24 для сверки (карта пишется и туда, и в 1С).",
    )

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Отправка карты в 1С"
        verbose_name_plural = "Отправки карт в 1С"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        who = " ".join(p for p in (self.last_name, self.first_name) if p) or "(без имени)"
        return f"{self.phone} · {who} · {self.status}"


class WeeklyPromo(models.Model):
    """Промо-акция недели от СММ-специалиста для блока «скидки, акции и новинки».

    Одна запись на ISO-неделю. Хранит и контент акции, и состояние диалога с
    специалистом (статусы), чтобы переживать перезапуск процесса-поллера - state
    не в памяти. В рассылку попадает только status == confirmed.
    """

    STATUS_AWAITING = "awaiting_content"
    STATUS_REVIEW = "review"
    STATUS_CONFIRMED = "confirmed"
    STATUS_SENT = "sent"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_AWAITING, "Ждём контент"),
        (STATUS_REVIEW, "На согласовании"),
        (STATUS_CONFIRMED, "Подтверждено"),
        (STATUS_SENT, "Разослано"),
        (STATUS_CANCELLED, "Отменено"),
    ]

    week_key = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
        help_text="ISO неделя, например 2026-W28. Один промо на неделю.",
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_AWAITING, db_index=True
    )
    text = models.TextField(blank=True, help_text="Текст акции от специалиста.")
    image = models.ImageField(
        upload_to="care_promo/",
        blank=True,
        help_text="Присланная картинка акции. Даёт публичный URL для всех каналов.",
    )
    tg_file_id = models.CharField(
        max_length=256,
        blank=True,
        help_text="Telegram file_id исходной картинки (подстраховка, если скачать не удалось).",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Промо-акция недели"
        verbose_name_plural = "Промо-акции недели"
        ordering = ["-week_key"]

    def __str__(self) -> str:
        return f"{self.week_key} · {self.status}"

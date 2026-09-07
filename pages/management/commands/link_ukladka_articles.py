"""Перелинковка статей из БД на лендинг укладки (/ukladka-rulonnogo-gazona/).

Четыре статьи про газон живут в модели Article (загружены через API контент-
фабрики), поэтому правкой data.py их не тронуть. Команда дописывает в конец
sections статьи секцию с абзацем-ссылкой: before + <a>анкор</a> + after
(рендерится в templates/pages/stati-detail.html).

Идемпотентна: если ссылка на /ukladka-rulonnogo-gazona/ в статье уже есть,
статья пропускается. Анкоры разные по таблице «Перелинковка» из SEO-ТЗ W37.

    python manage.py link_ukladka_articles --dry-run
    python manage.py link_ukladka_articles
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

UKLADKA_URL = "/ukladka-rulonnogo-gazona/"

# slug статьи в БД -> абзац со ссылкой (анкоры из таблицы «Перелинковка» ТЗ).
ARTICLE_LINKS: dict[str, dict[str, str]] = {
    "kak-ulozhit-rulonnyy-gazon": {
        "heading": "Если укладывать будем мы",
        "before": (
            "Технология выше рабочая, но требует техники, людей и точного режима полива. "
            "Если проще отдать участок бригаде, можно "
        ),
        "anchor": "заказать укладку рулонного газона",
        "after": (
            ": приедем на замер, подготовим основание, уложим, прикатаем "
            "и сделаем первый полив."
        ),
    },
    "skolko-stoit-rulonnyy-gazon-pod-klyuch": {
        "heading": "Сколько стоит работа",
        "before": (
            "Цифры выше касаются материала. Работы по участку считаются отдельно, "
            "смотрите "
        ),
        "anchor": "цены на укладку с материалом",
        "after": ": там таблица по объёму и порядок расчёта сметы после замера.",
    },
    "uhod-za-rulonnym-gazonom-posle-ukladki": {
        "heading": "Когда за результат отвечаем мы",
        "before": (
            "Половина проблем первого месяца родом из укладки, а не из ухода. "
            "Когда участок готовим и стелим мы, это "
        ),
        "anchor": "укладка с гарантией приживаемости",
        "after": ": отвечаем и за материал, и за работу.",
    },
    "podgotovka-uchastka-pod-rulonnyy-gazon": {
        "heading": "Проверить основание до заказа",
        "before": (
            "Если участок после стройки и непонятно, что за грунт оставили строители, "
            "начните с выезда агронома: "
        ),
        "anchor": "аудит основания перед укладкой",
        "after": " покажет, хватит ли планировки или нужен завоз грунта и дренаж.",
    },
}


def section_for(slug: str) -> dict:
    link = ARTICLE_LINKS[slug]
    return {
        "heading": link["heading"],
        "links": [{
            "href": UKLADKA_URL,
            "anchor": link["anchor"],
            "before": link["before"],
            "after": link["after"],
        }],
    }


def already_linked(sections) -> bool:
    """Есть ли уже ссылка на лендинг укладки в теле статьи."""
    for section in sections or []:
        if not isinstance(section, dict):
            continue
        for link in section.get("links") or []:
            if isinstance(link, dict) and link.get("href") == UKLADKA_URL:
                return True
    return False


class Command(BaseCommand):
    help = "Дописывает в статьи из БД абзац со ссылкой на /ukladka-rulonnogo-gazona/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, что будет изменено, но ничего не сохранять.",
        )

    def handle(self, *args, **options):
        from pages.models import Article

        dry_run = options["dry_run"]
        added = skipped = missing = 0

        for slug in ARTICLE_LINKS:
            article = Article.objects.filter(slug=slug).first()
            if article is None:
                missing += 1
                self.stdout.write(self.style.WARNING(f"нет в БД: {slug}"))
                continue
            sections = list(article.sections or [])
            if already_linked(sections):
                skipped += 1
                self.stdout.write(f"уже есть ссылка: {slug}")
                continue
            if dry_run:
                added += 1
                self.stdout.write(self.style.NOTICE(f"добавил бы ссылку: {slug}"))
                continue
            sections.append(section_for(slug))
            article.sections = sections
            article.save(update_fields=["sections"])
            added += 1
            self.stdout.write(self.style.SUCCESS(f"ссылка добавлена: {slug}"))

        suffix = " (dry-run, ничего не сохранено)" if dry_run else ""
        self.stdout.write(
            f"Итого: добавлено {added}, пропущено {skipped}, нет в БД {missing}{suffix}"
        )

"""Синтез hero-врезки дайджеста из тем работ, выпадающих на ISO-неделю.

Раньше hero был двумя захардкоженными текстами на весь год (активный сезон и
межсезонье), выбор по месяцу - поэтому всю весну и лето подписчик получал один
и тот же абзац про «заморозки в конце мая». Этот модуль строит врезку из реальных
тем недели: «розы - бутоны и защита; газон набирает плотность; деревья -
формирование кроны». Если на неделе работ нет (межсезонье) - текст про
планирование следующего сезона с названием текущего месяца.

Модуль чистый, без Django: на вход словарь {ярлык категории: [темы]} и границы
недели. Live-путь (digest.py) и офлайн-генерация (scripts/) строят этот словарь
по-своему, но текст собирают одной функцией - hero одинаков везде.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter

# Порядок категорий в hero (как на сайте и в подписке).
CATEGORY_ORDER = ["Деревья", "Кустарники", "Многолетники", "Розы", "Газон"]

_MONTHS_GEN = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}
_MONTHS_NOM = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}

ACTIVE_TITLE = "Что важно успеть на этой неделе"
OFF_TITLE = "Что делать в межсезонье"

_PHRASE_MAX = 52
_TAIL = "Ниже подробные рекомендации по группам, на которые вы подписаны."


def date_range_display(start: dt.date, end: dt.date) -> str:
    """'16-21 июня' либо '28 июня - 4 июля' для разных месяцев."""
    if start.month == end.month:
        return f"{start.day}-{end.day} {_MONTHS_GEN[start.month]}"
    return f"{start.day} {_MONTHS_GEN[start.month]} - {end.day} {_MONTHS_GEN[end.month]}"


def _pick_phrase(themes: list[str]) -> str:
    """Самая частая осмысленная тема категории, в нижнем регистре, обрезанная."""
    norm = [(t or "").strip() for t in themes if (t or "").strip()]
    if not norm:
        return ""
    phrase = Counter(norm).most_common(1)[0][0]
    phrase = phrase[0].lower() + phrase[1:] if phrase else phrase
    if len(phrase) > _PHRASE_MAX:
        phrase = phrase[:_PHRASE_MAX].rsplit(" ", 1)[0] + "…"
    return phrase


def summarize_categories(cat_to_themes: dict[str, list[str]]) -> list[tuple[str, str]]:
    """[(ярлык, фраза)] в порядке CATEGORY_ORDER, только непустые категории."""
    out: list[tuple[str, str]] = []
    for label in CATEGORY_ORDER:
        themes = cat_to_themes.get(label)
        if not themes:
            continue
        phrase = _pick_phrase(themes)
        if phrase:
            out.append((label, phrase))
    return out


def _join_parts(parts: list[tuple[str, str]]) -> str:
    chunks = []
    for label, phrase in parts:
        low = label.lower()
        # «газон - газон набирает плотность» -> «газон набирает плотность»
        if phrase.lower().startswith(low):
            chunks.append(phrase)
        else:
            chunks.append(f"{low} - {phrase}")
    return "; ".join(chunks)


def build_hero(
    week_start: dt.date,
    week_end: dt.date,
    cat_to_themes: dict[str, list[str]],
) -> tuple[str, str]:
    """Возвращает (title, text) hero-врезки для недели.

    Есть работы -> активная врезка из тем недели. Нет -> межсезонье с названием
    месяца. Текст без длинного тире, диапазоны через дефис.
    """
    parts = summarize_categories(cat_to_themes)
    if not parts:
        month = _MONTHS_NOM[week_start.month]
        text = (
            f"{month}: открытых работ в саду сейчас немного. Это лучшее время "
            "спланировать следующий сезон - пересмотреть схему посадок, отметить, "
            "какие места просят обновления, и подобрать сорта."
            f"\n\n{_TAIL}"
        )
        return OFF_TITLE, text

    rng = date_range_display(week_start, week_end)
    body = _join_parts(parts)
    text = (
        f"{rng} в саду под Новосибирском. Главное на этой неделе: {body}."
        f"\n\n{_TAIL}"
    )
    return ACTIVE_TITLE, text

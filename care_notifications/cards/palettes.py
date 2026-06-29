"""Палитры сезонов и иконки карточек Службы заботы (значения из zabota.pen)."""
from __future__ import annotations

PALETTES = {
    "summer": dict(bg="#2D6A4F", bg_accent="#40916C", accent="#E9C46A",
                   accent_ink="#1B4332", ink="#1B4332", surface="#F4F1EA",
                   body_on_dark="#D8E5DE", muted="#5A7A6A",
                   kicker="#E9C46A", cta_bg="#E9C46A", cta_ink="#1B4332"),
    "spring": dict(bg="#43A05F", bg_accent="#7BC894", accent="#6E9BE6",
                   accent_ink="#15355C", ink="#2C6B43", surface="#F2F8F1",
                   body_on_dark="#E7F4EA", muted="#6FA588",
                   kicker="#FFFFFF", cta_bg="#FFFFFF", cta_ink="#2C6B43"),
    "autumn": dict(bg="#A85532", bg_accent="#C77E4A", accent="#F0C055",
                   accent_ink="#4A2410", ink="#4A2E1C", surface="#F8EFE4",
                   body_on_dark="#F2E0CF", muted="#9C6A47",
                   kicker="#F0C055", cta_bg="#F0C055", cta_ink="#4A2410"),
    "winter": dict(bg="#1F4A5A", bg_accent="#36707F", accent="#BFE2EA",
                   accent_ink="#143038", ink="#1E3A44", surface="#EEF4F6",
                   body_on_dark="#D2E6EC", muted="#6B919C",
                   kicker="#BFE2EA", cta_bg="#BFE2EA", cta_ink="#143038"),
}

SEASON_EMBLEM = {"summer": "sun", "spring": "flower-2", "autumn": "leaf", "winter": "snowflake"}

CATEGORY_ICON = {
    "derevya": "tree-deciduous",
    "kustarniki": "trees",
    "mnogoletniki": "flower-2",
    "rozy": "flower",
    "gazon": "sprout",
    "seasonal": "calendar-heart",
}

CATEGORY_LABEL_FALLBACK = {
    "derevya": "Деревья",
    "kustarniki": "Кустарники",
    "mnogoletniki": "Многолетники",
    "rozy": "Розы",
    "gazon": "Газон и злаки",
}

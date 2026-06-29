"""Двухформатный шейпер контента карточки Службы заботы.

Формат A: theme пустой, маркер «Что важно:- a- b- c», даты диапазоном.
Формат B: theme заполнен осмысленной фразой - сам theme = готовый пункт.
"""
from __future__ import annotations

import re

_CUES = ("что важно сейчас", "что важно", "что можно сделать", "что нужно сделать",
         "что нужно", "что сделать", "что делаем", "что делать", "что учесть",
         "что поддержит эффект", "рекомендации")

_STOP = re.compile(r"[👉🌱✅⚠️ℹ️📌🛒⚡💦💡🧹🌲#*]")

_LEAD_EMOJI = re.compile(
    r"^[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    r"←-⇿⬀-⯿️‍\s]+"
)

_WEAK = {
    "при необходимости", "по желанию", "возможно", "по необходимости",
    "и наблюдение", "наблюдение", "при желании", "далее", "затем",
    "если нужно", "при появлении", "по ситуации",
}


def _clean(s: str) -> str:
    s = _LEAD_EMOJI.sub("", s)
    s = s.strip(" .;:·•-–\n\t")
    s = re.sub(r"\s+", " ", s)
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    return s


def _is_weak(s: str) -> bool:
    return s.strip().lower() in _WEAK or len(s) < 5


def _state_line(text: str) -> str:
    low = text.lower()
    for cue in _CUES:
        i = low.find(cue)
        if i > 0:
            head = text[:i]
            head = re.split(r"Сообщение\s*:?", head)[0]
            m = re.search(r"[а-яё][А-ЯЁ]", head)
            if m:
                head = head[: m.start() + 1]
            return _clean(head.split("\n")[0])
    return ""


def has_cue(text: str) -> bool:
    low = (text or "").lower()
    return any(c in low for c in _CUES)


def shape_format_a(text: str, *, max_bullets: int = 3) -> dict:
    low = text.lower()
    cut = None
    for cue in _CUES:
        i = low.find(cue)
        if i >= 0:
            colon = text.find(":", i)
            cut = (colon + 1) if 0 <= colon - i <= len(cue) + 2 else i + len(cue)
            break
    if cut is None:
        return {"headline": "", "bullets": []}
    body = text[cut:]
    stop = _STOP.search(body)
    if stop:
        body = body[: stop.start()]
    raw = re.split(r"(?:(?<=\S)-\s*|\s-\s*|•\s*|\n)", body)
    bullets = []
    for r in raw:
        seg = r.strip()
        if not seg:
            continue
        if _LEAD_EMOJI.match(seg) and _LEAD_EMOJI.sub("", seg):
            continue
        b = _clean(r)
        if b and not _is_weak(b) and b not in bullets:
            bullets.append(b)
        if len(bullets) >= max_bullets:
            break
    return {"headline": _state_line(text), "bullets": bullets}


def shape_period(content_text: str, theme: str) -> dict:
    text = (content_text or "").strip()
    th = (theme or "").strip()
    if has_cue(text):
        r = shape_format_a(text)
        if r["bullets"]:
            return {"kind": "a", "headline": r["headline"],
                    "bullets": r["bullets"], "topic": th}
    if th:
        return {"kind": "b", "headline": "", "bullets": [], "topic": _clean(th)}
    return {"kind": "none", "headline": "", "bullets": [], "topic": ""}


def build_category_card(periods: list[tuple[str, str]], *,
                        fallback_headline: str, max_bullets: int = 3) -> dict:
    headline = ""
    bullets: list[str] = []
    topics: list[str] = []
    for content_text, theme in periods:
        sp = shape_period(content_text, theme)
        if sp["kind"] == "a":
            if not headline and sp["headline"]:
                headline = sp["headline"]
            for b in sp["bullets"]:
                if b not in bullets:
                    bullets.append(b)
        elif sp["kind"] == "b" and sp["topic"]:
            if sp["topic"] not in topics:
                topics.append(sp["topic"])
    for t in topics:
        if len(bullets) >= max_bullets:
            break
        if t not in bullets:
            bullets.append(t)
    return {"headline": headline or fallback_headline, "bullets": bullets[:max_bullets]}

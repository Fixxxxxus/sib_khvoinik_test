#!/usr/bin/env python3
"""
Parse 115 Yonote plant-care documents into structured calendar data.

Reads /tmp/yonote_all_115_markdown.json (exported Markdown with images),
falls back to /tmp/yonote_all_115.json (plain text).
Categorises plants, extracts seasonal care periods, and writes
pages/calendar_data.py.
"""

import html as html_mod
import json
import re
import textwrap
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────
SRC_MD = Path("/tmp/yonote_all_115_markdown.json")
SRC_PLAIN = Path("/tmp/yonote_all_115.json")
DST = Path(__file__).resolve().parent.parent / "pages" / "calendar_data.py"

# ── transliteration table ──────────────────────────────────────────────
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
    "ё": "yo", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}


def transliterate(text: str) -> str:
    out = []
    for ch in text.lower():
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        elif ch.isascii() and (ch.isalnum() or ch in "-_ "):
            out.append(ch)
        else:
            out.append(" ")
    return "".join(out)


def slugify(text: str) -> str:
    t = transliterate(text)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    t = re.sub(r"-{2,}", "-", t)
    return t[:80]


# ── category classification ───────────────────────────────────────────

CATEGORY_DEFS = [
    (
        "derevya",
        "Деревья",
        [
            "хвойные деревья",
            "лиственные декоративные деревья",
            "яблони декоративные",
            "рябина обыкновенная",
            "клён",
            "черёмуха",
            "черёмухой",
        ],
    ),
    (
        "rozy",
        "Розы",
        [
            "розы (все группы",
            "роза морщинистая",
        ],
    ),
    (
        "gazon",
        "Газон и злаки",
        [
            "рулонный газон",
            "злаки",
            "вейник",
            "императа",
        ],
    ),
    (
        "kustarniki",
        "Кустарники",
        [
            "кустарниками",
            "кустарники",
            "гортензия",
            "гортензией",
            "hydrangea",
            "спирея",
            "барбарис",
            "чубушник",
            "снежноягодник",
            "лох серебристый",
            "миндаль",
            "рябинник",
            "сирень",
            "лапчатка кустарниковая",
            "лапчаткой кустарниковой",
        ],
    ),
]


def classify(title: str) -> str:
    low = title.lower()
    for slug, _label, keywords in CATEGORY_DEFS:
        for kw in keywords:
            if kw in low:
                return slug
    return "mnogoletniki"


# ── name parsing ──────────────────────────────────────────────────────

# Instrumental → Nominative case mapping for plant names
_INSTR_TO_NOM = {
    "лиственными кустарниками": "Лиственные кустарники",
    "декоративными злаками": "Декоративные злаки",
    "гортензией метельчатой": "Гортензия метельчатая",
    "гортензией крупнолистной": "Гортензия крупнолистная",
    "гортензией": "Гортензия",
    "мордовником обыкновенным": "Мордовник обыкновенный",
    "медуницей сахарной": "Медуница сахарная",
    "манжеткой мягкой": "Манжетка мягкая",
    "люпином многолистным": "Люпин многолистный",
    "лилейником гибридным": "Лилейник гибридный",
    "лапчаткой гибридной": "Лапчатка гибридная",
    "декоративным луком": "Декоративный лук",
    "ландышем майским": "Ландыш майский",
    "купальницей": "Купальница",
    "книфофией гибридной": "Книфофия гибридная",
    "кровохлёбкой лекарственной": "Кровохлёбка лекарственная",
    "клопогоном кистевидным": "Клопогон кистевидный",
    "кореопсисом крупноцветковым": "Кореопсис крупноцветковый",
    "колокольчиком скученным": "Колокольчик скученный",
    "колокольчиком персиколистным": "Колокольчик персиколистный",
    "клематисом": "Клематис",
    "ирисом сибирским": "Ирис сибирский",
    "живучкой ползучей": "Живучка ползучая",
    "дербенником прутовидным": "Дербенник прутовидный",
    "дербенником иволистным": "Дербенник иволистный",
    "дельфиниумом": "Дельфиниум",
    "гравилатом чилийским": "Гравилат чилийский",
    "геранью кроваво-красной": "Герань кроваво-красная",
    "геранью кантабрийской": "Герань кантабрийская",
    "геранью гималайской": "Герань гималайская",
    "геранью гибридной": "Герань гибридная",
    "гейхерой гибридной": "Гейхера гибридная",
    "гвоздикой гибридной": "Гвоздика гибридная",
    "гайлардией остистой": "Гайлардия остистая",
    "вероникаструмом сибирским": "Вероникаструм сибирский",
    "вероникаструмом виргинским": "Вероникаструм виргинский",
    "вероникой колосковой": "Вероника колосковая",
    "вероникой колосистой": "Вероника колосистая",
    "вероникой длиннолистной": "Вероника длиннолистная",
    "вербейником точечным": "Вербейник точечный",
    "бузульником зубчатым": "Бузульник зубчатый",
    "бруннерой крупнолистной": "Бруннера крупнолистная",
    "барвинком малым": "Барвинок малый",
    "баданом сердцелистным": "Бадан сердцелистный",
    "баданом гибридным": "Бадан гибридный",
    "астрой кустарниковой": "Астра кустарниковая",
    "астильбой": "Астильба",
    "астильбой китайской": "Астильба китайская",
    "армерией приморской": "Армерия приморская",
    "анемоной корончатой": "Анемона корончатая",
    "анемоной гибридной": "Анемона гибридная",
    "аквилегией": "Аквилегия",
    "агапантусом": "Агапантус",
    "астильбой арендса": "Астильба Арендса",
    "астильбой китайской": "Астильба китайская",
    "астильбой": "Астильба",
    "астрой кустарниковой": "Астра кустарниковая",
    "астра ново-английская": "Астра ново-английская",  # typo in source (already nom)
    "армерией приморской": "Армерия приморская",
    "анемоной корончатой": "Анемона корончатая",
    "анемоной гибридной": "Анемона гибридная",
    "аквилегией": "Аквилегия",
    "сиренью": "Сирень",
    "лапчаткой кустарниковой": "Лапчатка кустарниковая",
    "черёмухой шуберта": "Черёмуха Шуберта",
    "черёмухой": "Черёмуха",
}

# Latin name regex — captures genuine botanical Latin names
# Strategy: look for Latin in parentheses first "(Genus species)", then after Russian text
_LATIN_PAREN_RE = re.compile(
    r"\(([A-Z][a-z]{2,}(?:\s+[a-z×][a-z]+)+)\)"  # "(Genus species)" — require at least 2 words
)
_LATIN_AFTER_RUS_RE = re.compile(
    r"[а-яёА-ЯЁ)\s]([A-Z][a-z]{2,}(?:\s+[a-z×-]+)+)"  # After Russian: "Genus species" (allow hyphens for novae-angliae)
)
_LATIN_STANDALONE_RE = re.compile(
    r"(?:[\s(]|^)([A-Z][a-z]{4,})"  # Standalone genus 5+ chars, only as fallback
)

# Regex to find Latin starting right after Russian (no space/paren)
_LATIN_GLUED_RE = re.compile(
    r"([а-яёА-ЯЁ)])([A-Z][a-z]+(?:\s+[a-z×]+)*)"
)

# Clean title prefixes — handles both "Календарь ухода за " and "CRM-календарь уходаЛох"
_PREFIX_RE = re.compile(
    r"^(?:🌿\s*)?(?:CRM-)?[Кк]алендарь(?:\s*ухода)?(?:\s+за)?\s*:?\s*",
    re.IGNORECASE,
)

# Pattern to extract "Сорта: ..." or "Сорт: ..." from title
_SORTA_RE = re.compile(r"[Сс]орт[аы]?:\s*(.+?)(?:\s*$|\s*[Рр]егион|\s*[Рр]азмер)")


def parse_name(title: str):
    """Return (russian_name, latin_name_or_empty, varieties_list)."""
    # Strip prefix
    clean = _PREFIX_RE.sub("", title).strip()

    # Insert space before glued Latin names (e.g. "кустарниковойPotentilla")
    clean = _LATIN_GLUED_RE.sub(r"\1 \2", clean)

    # Extract Latin name — try in order of specificity
    # Only search before "Сорта:" / "Сорт:" to avoid matching cultivar names
    latin = ""
    varieties = []
    clean_for_latin = re.split(r"[Сс]орт[аы]?:", clean)[0]

    # 1. Try parenthesised Latin: "(Genus species)"
    lat_match = _LATIN_PAREN_RE.search(clean_for_latin)
    if lat_match:
        latin = lat_match.group(1).strip()
    else:
        # 2. Try "Genus species" after Russian text
        lat_match = _LATIN_AFTER_RUS_RE.search(clean_for_latin)
        if lat_match:
            latin = lat_match.group(1).strip()
        else:
            # 3. Fallback: standalone genus (5+ chars)
            lat_match = _LATIN_STANDALONE_RE.search(clean_for_latin)
            if lat_match:
                latin = lat_match.group(1).strip()

    # Extract additional cultivar names from quotes (various quote styles)
    # Use proper paired quotes first, then double-quotes
    quoted = re.findall(r'[«\u201c]([^»\u201d]+)[»\u201d]', clean)
    quoted += re.findall(r'"([^"]+)"', clean)
    for q in quoted:
        q = q.strip()
        if q and len(q) > 1 and q not in varieties:
            varieties.append(q)

    # Extract from "Сорта: X, Y, Z" or "Сорт: X" patterns in title
    sorta_match = _SORTA_RE.search(clean)
    if sorta_match:
        sorta_text = sorta_match.group(1).strip()
        # Split by comma, strip each
        for s in sorta_text.split(","):
            s = s.strip().strip('"\'«»\u201c\u201d')
            if s and s not in varieties:
                varieties.append(s)

    # Russian name: extract portion before Latin text
    # First, find where Latin portion starts
    lat_start_match = re.search(r'[\s(][A-Z][a-z]', clean)
    if lat_start_match:
        rus_part = clean[: lat_start_match.start()].strip()
    else:
        rus_part = clean

    # Strip trailing quotes/parentheses from Russian part
    rus_part = re.sub(r'\s*[«"\u201c\u2018\'"\(].*$', "", rus_part).strip()
    rus_part = rus_part.rstrip("(").strip()
    rus_part = re.sub(r"\s{2,}", " ", rus_part).strip()

    # Remove trailing "(ассортимент)", "(все ...)" etc.
    rus_part = re.sub(r"\s*\(.*$", "", rus_part).strip()
    # Remove "Сорта: ...", "Сорт: ...", "Регион: ...", "Группы: ..." from end
    rus_part = re.sub(r"\s*[Сс]орт[аы]?:.*$", "", rus_part).strip()
    rus_part = re.sub(r"\s*[Рр]егион:.*$", "", rus_part).strip()
    rus_part = re.sub(r"\s*[Гг]руппы?:.*$", "", rus_part).strip()
    rus_part = re.sub(r"\s*[Вв]иды и сорта:.*$", "", rus_part).strip()
    # Remove trailing "(серия ...)" etc
    rus_part = re.sub(r"\s*\(серия.*$", "", rus_part).strip()

    if not rus_part:
        rus_part = clean.split("(")[0].strip()
        # Still try to get Russian portion only
        lat_start_match2 = re.search(r'[A-Z][a-z]', rus_part)
        if lat_start_match2:
            rus_part = rus_part[: lat_start_match2.start()].strip()

    # Strip region info
    rus_part = re.sub(r"\s*Новосибирская область.*$", "", rus_part).strip()
    rus_part = re.sub(r"\s*\(Новосибирская область\)", "", rus_part).strip()

    # Apply instrumental → nominative mapping (longest match first)
    rus_lower = rus_part.lower()
    for instr, nom in sorted(_INSTR_TO_NOM.items(), key=lambda x: -len(x[0])):
        if rus_lower == instr or rus_lower.startswith(instr):
            rus_part = nom + rus_part[len(instr):]
            break

    # Capitalize first letter
    if rus_part and rus_part[0].islower():
        rus_part = rus_part[0].upper() + rus_part[1:]

    if not rus_part:
        rus_part = clean.split("(")[0].split("[")[0].strip()

    return rus_part, latin, varieties


# ── period parsing ────────────────────────────────────────────────────

MONTHS = {
    "января": "января",
    "февраля": "февраля",
    "марта": "марта",
    "апреля": "апреля",
    "мая": "мая",
    "июня": "июня",
    "июля": "июля",
    "августа": "августа",
    "сентября": "сентября",
    "октября": "октября",
    "ноября": "ноября",
    "декабря": "декабря",
}

MONTH_NAMES = "|".join(MONTHS.keys())

# Promo keywords to filter out
_PROMO_KEYWORDS = [
    "уже есть", "уже в наличии", "можно подобрать",
    "уже доступн", "уже поступил", "можно быстро",
    "поможем выбрать", "подберём", "подскажем",
    "можно подготовиться", "удобно обновить",
    "поможем подобрать", "подберём под",
]

# ── Markdown date header pattern ─────────────────────────────────────
# Matches: ## **20 апреля**, ## 📅 25 апреля – 15 мая, ## 5-15 мая, etc.
_MD_DATE_HEADER_RE = re.compile(
    r"^##\s+(?:📅\s*)?(?:\*{1,2})?"
    r"(\d{1,2}\s*(?:" + MONTH_NAMES + r")?"
    r"(?:\s*[–—\-]\s*\d{1,2}\s*(?:" + MONTH_NAMES + r"))?)"
    r"(?:\*{1,2})?\s*$",
    re.MULTILINE,
)

# Plain-text date label (for fallback plain-text mode)
_PLAIN_DATE_RE = re.compile(
    r"^(?:📅\s*)?(\d{1,2}\s*(?:" + MONTH_NAMES + r")\s*"
    r"(?:[–—\-]\s*\d{1,2}\s*(?:" + MONTH_NAMES + r"))?)\s*$"
)


def _normalize_date_label(raw: str) -> str:
    """Clean up a date label: normalise dashes, strip emoji/bold markers."""
    label = re.sub(r"^\*+|\*+$", "", raw).strip()
    label = re.sub(r"^📅\s*", "", label).strip()
    label = re.sub(r"\s*[–—\-]\s*", " – ", label).strip()
    return label


def _is_promo_line(line: str) -> bool:
    """Return True if line is a promotional/CTA line to skip."""
    stripped = line.strip()
    if not stripped:
        return False
    text_only = re.sub(r"^[^\w]+", "", stripped).strip().lower()
    return any(kw in text_only for kw in _PROMO_KEYWORDS)


def _esc(text: str) -> str:
    """Escape HTML entities."""
    return html_mod.escape(text, quote=False)


def _md_inline(text: str) -> str:
    """Convert inline markdown to HTML: **bold**, *italic*, [link](url)."""
    text = _esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    return text


def _md_block_to_html(block_lines: list[str]) -> str:
    """Convert a list of markdown lines into HTML."""
    if not block_lines:
        return ""

    result: list[str] = []
    paragraph: list[str] = []
    in_list = False

    def flush_para():
        nonlocal paragraph
        if paragraph:
            result.append("<p>" + "<br>".join(paragraph) + "</p>")
            paragraph = []

    def flush_list():
        nonlocal in_list
        if in_list:
            result.append("</ul>")
            in_list = False

    for line in block_lines:
        stripped = line.strip()

        if not stripped:
            flush_list()
            flush_para()
            continue

        # List item: - text or * text (including nested)
        list_match = re.match(r"^\s*[-*]\s+(.+)", stripped)
        if list_match:
            flush_para()
            if not in_list:
                result.append('<ul class="list-disc ml-5 space-y-1">')
                in_list = True
            result.append(f"<li>{_md_inline(list_match.group(1).strip())}</li>")
            continue

        # 👉 tip lines
        if stripped.startswith("👉"):
            flush_list()
            flush_para()
            tip = stripped[len("👉"):].strip()
            result.append(
                f'<div class="mt-2 flex gap-2 text-brand">'
                f"<span>👉</span><span>{_esc(tip)}</span></div>"
            )
            continue

        # Regular paragraph line
        flush_list()
        paragraph.append(_md_inline(stripped))

    flush_list()
    flush_para()
    return "\n".join(result)


def parse_periods_markdown(md_text: str):
    """Parse periods from a Markdown-exported Yonote document."""
    matches = list(_MD_DATE_HEADER_RE.finditer(md_text))
    if not matches:
        return []

    periods = []
    for i, m in enumerate(matches):
        date_label = _normalize_date_label(m.group(1))
        if not date_label or not re.search(MONTH_NAMES, date_label):
            continue

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        block = md_text[start:end].strip()
        block = re.sub(r"\n---\s*$", "", block).strip()

        # Theme
        theme = ""
        theme_m = re.search(r"###\s*[Тт]ема:\s*(.+)", block)
        if theme_m:
            theme = theme_m.group(1).strip()

        # Remove structural headers (### Тема:, ### Сообщение:)
        block = re.sub(r"###\s*[Тт]ема:\s*.+\n?", "", block)
        block = re.sub(r"###\s*[Сс]ообщение:\s*\n?", "", block)

        # Extract images: ![alt](url "title")
        images = []
        for img_m in re.finditer(r"!\[[^\]]*\]\(([^)\"]+)(?:\s+\"[^\"]*\")?\)", block):
            url = img_m.group(1).strip()
            if url:
                images.append(url)
        block = re.sub(r"\s*!\[[^\]]*\]\([^)]+\)\s*", "\n", block)

        # Extract videos
        videos = []
        kept_lines = []
        for line in block.split("\n"):
            stripped = line.strip()
            is_video = "🎥" in stripped or stripped.lower().startswith("видео")
            is_yt = bool(re.search(
                r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)", stripped
            ))
            if is_video or is_yt:
                vt = re.sub(r"^🎥\s*", "", stripped).strip()
                vt = re.sub(r"^[Вв]идео[-:]?\s*", "", vt).strip()
                vt = re.sub(r"^\*+|\*+$", "", vt).strip()  # strip bold
                if vt:
                    url_m = re.search(r"(https?://[^\s)]+)", vt)
                    if url_m:
                        url = url_m.group(1)
                        label = vt.replace(url, "").strip().rstrip(":").strip()
                        videos.append({"label": label or "Смотреть видео", "url": url})
                    else:
                        videos.append({"label": vt, "url": ""})
            else:
                kept_lines.append(line)

        # Extract products (bold list items that look like product names)
        products = []
        content_lines = []
        for line in kept_lines:
            stripped = line.strip()

            # Skip promo lines
            if stripped and stripped[0] in "💡✨🌱🌸🌿⚡🍂🛡🧪":
                if _is_promo_line(stripped):
                    continue
            if _is_promo_line(stripped):
                continue

            # Product detection: bold items in lists with dosage
            if re.search(r"\d+\s*[-–]?\s*\d*\s*(г|мл|таблетк|капл)", stripped):
                prod = re.sub(r"^[-*]\s+", "", stripped)
                prod = re.sub(r"\*\*(.+?)\*\*", r"\1", prod)  # strip bold
                products.append(prod.strip())
                continue

            content_lines.append(line)

        # Convert content to HTML
        content_html = _md_block_to_html(content_lines)
        # Plain text fallback
        content_text = re.sub(r"<[^>]+>", "", content_html).strip()
        content_text = re.sub(r"\n{3,}", "\n\n", content_text)

        periods.append({
            "date_label": date_label,
            "theme": theme,
            "content_text": content_text,
            "content_html": content_html,
            "images": images,
            "products": products,
            "videos": videos,
        })

    return periods


def parse_periods_plain(text: str):
    """Fallback: parse periods from plain text (documents.list format)."""
    lines = text.split("\n")
    periods = []
    current = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # Try to parse as date label
        dm = _PLAIN_DATE_RE.match(line)
        if dm:
            date_label = _normalize_date_label(dm.group(1))
            if date_label and re.search(MONTH_NAMES, date_label):
                if current:
                    _finalize_plain_period(current)
                    periods.append(current)
                current = {
                    "date_label": date_label,
                    "theme": "",
                    "content_lines": [],
                    "products": [],
                    "videos": [],
                    "images": [],
                }
                continue

        if current is None:
            continue

        # Theme
        tm = re.match(r"^[Тт]ема:\s*(.+)", line)
        if tm and not current["theme"]:
            current["theme"] = tm.group(1).strip()
            continue

        # Videos
        is_video = "🎥" in line or line.lower().startswith("видео")
        is_yt = bool(re.search(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)", line))
        if is_video or is_yt:
            vt = re.sub(r"^🎥\s*", "", line).strip()
            vt = re.sub(r"^[Вв]идео[-:]?\s*", "", vt).strip()
            if vt:
                url_m = re.search(r"(https?://[^\s]+)", vt)
                if url_m:
                    url = url_m.group(1)
                    label = vt.replace(url, "").strip().rstrip(":").strip()
                    current["videos"].append({"label": label or "Смотреть видео", "url": url})
                else:
                    current["videos"].append({"label": vt, "url": ""})
            continue

        # Products
        if re.search(r"\d+\s*[-–]?\s*\d*\s*(г|мл|таблетк|капл)", line) and "—" in line:
            current["products"].append(line)
            continue

        # Skip promo
        if line and line[0] in "💡✨🌱🌸🌿⚡🍂🛡🧪":
            continue
        if _is_promo_line(line):
            continue

        current["content_lines"].append(line)

    if current:
        _finalize_plain_period(current)
        periods.append(current)

    return periods


def _finalize_plain_period(p: dict):
    """Collapse content_lines into text/html for plain-text mode."""
    lines = p.pop("content_lines")
    if lines and re.match(r"^[Сс]ообщение:\s*$", lines[0]):
        lines = lines[1:]
    elif lines:
        lines[0] = re.sub(r"^[Сс]ообщение:\s*", "", lines[0])
    text = "\n".join(l.strip() for l in lines).strip()
    p["content_text"] = text
    p["content_html"] = _md_block_to_html(lines)


# ── main logic ────────────────────────────────────────────────────────


def main():
    # Prefer markdown source (has images), fall back to plain text
    use_markdown = False
    if SRC_MD.exists():
        docs_md = json.loads(SRC_MD.read_text(encoding="utf-8"))
        # Build id→markdown lookup
        md_lookup = {d["id"]: d["markdown"] for d in docs_md}
        print(f"Loaded {len(docs_md)} markdown exports from {SRC_MD}")
        use_markdown = True
    else:
        md_lookup = {}

    docs = json.loads(SRC_PLAIN.read_text(encoding="utf-8"))
    print(f"Loaded {len(docs)} documents from {SRC_PLAIN}")
    if use_markdown:
        print(f"Using MARKDOWN source (images + formatting)")
    else:
        print(f"Using PLAIN TEXT source (no images)")

    # Build plants
    plants = []
    slug_counts: dict[str, int] = {}
    all_date_labels: list[str] = []
    category_counts: dict[str, int] = {}

    for doc in docs:
        title = doc["title"]
        yonote_id = doc["id"]

        cat_slug = classify(title)
        category_counts[cat_slug] = category_counts.get(cat_slug, 0) + 1

        rus_name, latin, varieties = parse_name(title)
        base_slug = slugify(rus_name) if rus_name else slugify(title)
        if not base_slug:
            base_slug = "plant"

        # Deduplicate slug
        if base_slug in slug_counts:
            slug_counts[base_slug] += 1
            slug = f"{base_slug}-{slug_counts[base_slug]}"
        else:
            slug_counts[base_slug] = 1
            slug = base_slug

        # Parse periods from markdown if available, otherwise plain text
        md = md_lookup.get(yonote_id)
        if md:
            periods = parse_periods_markdown(md)
        else:
            periods = parse_periods_plain(doc["text"])
        for p in periods:
            dl = p["date_label"]
            if dl not in all_date_labels:
                all_date_labels.append(dl)

        plants.append({
            "slug": slug,
            "name": rus_name,
            "latin": latin,
            "varieties": varieties,
            "category_slug": cat_slug,
            "yonote_id": yonote_id,
            "periods": periods,
        })

    # Sort plants alphabetically within each category
    cat_order = ["derevya", "rozy", "gazon", "kustarniki", "mnogoletniki"]
    plants.sort(key=lambda p: (cat_order.index(p["category_slug"]) if p["category_slug"] in cat_order else 99, p["name"].lower()))

    # Build categories list
    cat_labels = {s: l for s, l, _ in CATEGORY_DEFS}
    cat_labels["mnogoletniki"] = "Многолетники"
    categories = []
    for slug in cat_order:
        count = category_counts.get(slug, 0)
        if count:
            categories.append({
                "slug": slug,
                "label": cat_labels.get(slug, slug),
                "count": count,
            })

    # Sort date labels chronologically
    MONTH_ORDER = {
        "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
        "мая": 5, "июня": 6, "июля": 7, "августа": 8,
        "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    }

    def date_sort_key(label: str):
        # Extract first number and first month
        nums = re.findall(r"\d+", label)
        months = re.findall(MONTH_NAMES, label)
        day = int(nums[0]) if nums else 0
        month = MONTH_ORDER.get(months[0], 0) if months else 0
        return (month, day)

    all_date_labels.sort(key=date_sort_key)

    # Stats
    total_periods = sum(len(p["periods"]) for p in plants)
    print(f"Plants: {len(plants)}")
    print(f"Categories: {[(c['slug'], c['count']) for c in categories]}")
    print(f"Unique period labels: {len(all_date_labels)}")
    print(f"Total periods across all plants: {total_periods}")

    # ── write output ──────────────────────────────────────────────────
    buf = []
    buf.append('"""')
    buf.append("Auto-generated calendar data from Yonote documents.")
    buf.append(f"Source: yonote  |  {len(plants)} plants  |  {total_periods} periods")
    buf.append('"""')
    buf.append("")

    # CALENDAR_CATEGORIES
    buf.append("CALENDAR_CATEGORIES = [")
    for cat in categories:
        buf.append(f"    {cat!r},")
    buf.append("]")
    buf.append("")

    # CALENDAR_PERIODS
    buf.append("CALENDAR_PERIODS = [")
    for dl in all_date_labels:
        buf.append(f"    {dl!r},")
    buf.append("]")
    buf.append("")

    # CALENDAR_PLANTS — write with reasonable formatting
    buf.append("CALENDAR_PLANTS = [")
    for plant in plants:
        buf.append("    {")
        buf.append(f"        \"slug\": {plant['slug']!r},")
        buf.append(f"        \"name\": {plant['name']!r},")
        buf.append(f"        \"latin\": {plant['latin']!r},")
        buf.append(f"        \"varieties\": {plant['varieties']!r},")
        buf.append(f"        \"category_slug\": {plant['category_slug']!r},")
        buf.append(f"        \"yonote_id\": {plant['yonote_id']!r},")
        buf.append(f"        \"periods\": [")
        for period in plant["periods"]:
            buf.append("            {")
            buf.append(f"                \"date_label\": {period['date_label']!r},")
            buf.append(f"                \"theme\": {period['theme']!r},")
            buf.append(f"                \"content_text\": {period['content_text']!r},")
            buf.append(f"                \"content_html\": {period['content_html']!r},")
            buf.append(f"                \"images\": {period.get('images', [])!r},")
            buf.append(f"                \"products\": {period['products']!r},")
            buf.append(f"                \"videos\": {period['videos']!r},")
            buf.append("            },")
        buf.append("        ],")
        buf.append("    },")
    buf.append("]")
    buf.append("")

    DST.write_text("\n".join(buf), encoding="utf-8")
    print(f"\nWrote {DST}  ({DST.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()

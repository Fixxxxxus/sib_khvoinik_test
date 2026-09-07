"""Минификация HTML на выдаче.

Шаблоны проекта отформатированы с отступами, из-за чего в прод уезжает много
лишних пробелов и переводов строк (на странице категории каталога - около 90 КБ
из 334 КБ). Middleware схлопывает пробельные последовательности прямо в ответе,
не трогая исходные шаблоны.

Что гарантированно остаётся нетронутым:
  * содержимое <pre>, <textarea>, <script> (включая application/ld+json), <style>;
  * условные комментарии IE (<!--[if ...]> ... <![endif]-->);
  * значимый пробел между инлайн-элементами - он схлопывается до одного,
    но никогда не удаляется полностью.

Обычные HTML-комментарии удаляются. Любая ошибка минификатора не роняет ответ:
отдаём исходный HTML и пишем traceback в лог.
"""

from __future__ import annotations

import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)


# Блоки, содержимое которых переносится в ответ байт в байт.
_PROTECTED_TAGS = ('pre', 'textarea', 'script', 'style')

# Один проход по документу: защищённый блок | комментарий | тег. Всё остальное -
# текстовые узлы. Регэксп тега умеет пропускать кавычки, чтобы '>' внутри
# значения атрибута не обрывал разбор.
_TOKEN_RE = re.compile(
    r'(?P<protected><(?P<ptag>' + '|'.join(_PROTECTED_TAGS) + r')\b[^>]*>[\s\S]*?</(?P=ptag)\s*>)'
    r'|(?P<comment><!--[\s\S]*?-->)'
    r'|(?P<tag><[a-zA-Z!/][^>"\']*(?:(?:"[^"]*"|\'[^\']*\')[^>"\']*)*>)',
    re.IGNORECASE,
)

_TAG_NAME_RE = re.compile(r'^</?\s*([a-zA-Z0-9!-]+)')

# Разбиение содержимого тега на кавычки и всё остальное: пробелы схлопываем
# только вне значений атрибутов, чтобы не портить value=" " и подобное.
_QUOTED_RE = re.compile(r'("[^"]*"|\'[^\']*\')')

_WS_RE = re.compile(r'\s+')
# Пробел перед закрывающей '>' убираем, а вот ' />' оставляем как есть:
# на такую запись самозакрывающихся тегов опираются существующие тесты разметки.
_WS_BEFORE_CLOSE_RE = re.compile(r'\s+>$')

# Теги, вокруг которых пробел не влияет на отрисовку: их можно вычищать целиком.
# Инлайновые (a, span, button, i, img, label, input, svg...) сюда осознанно не
# попадают - между ними пробел значим.
_BLOCK_TAGS = frozenset(
    """
    !doctype html head body div section article aside header footer nav main
    ul ol li dl dt dd p h1 h2 h3 h4 h5 h6 table thead tbody tfoot tr td th
    caption colgroup col form fieldset legend hr br script style link meta
    title noscript figure figcaption blockquote details summary dialog
    template address pre option optgroup
    """.split()
)


def _tag_name(tag: str) -> str:
    match = _TAG_NAME_RE.match(tag)
    return match.group(1).lower() if match else ''


def _is_conditional_comment(comment: str) -> bool:
    """Условные комментарии IE (в т.ч. downlevel-revealed) сохраняем как есть."""
    head = comment[:20].lower()
    return head.startswith('<!--[if') or head.startswith('<!--<![endif')


def _minify_tag(tag: str) -> str:
    """Схлопывает пробелы между атрибутами, не заглядывая внутрь кавычек."""
    parts = _QUOTED_RE.split(tag)
    for i in range(0, len(parts), 2):
        parts[i] = _WS_RE.sub(' ', parts[i])
    result = ''.join(parts)
    return _WS_BEFORE_CLOSE_RE.sub('>', result)


def minify_html(html: str) -> str:
    """Возвращает HTML со схлопнутыми пробелами и без обычных комментариев."""
    tokens: list[tuple[str, str, str]] = []  # (kind, text, tag_name)
    pos = 0
    for match in _TOKEN_RE.finditer(html):
        if match.start() > pos:
            tokens.append(('text', html[pos:match.start()], ''))
        if match.group('protected') is not None:
            tokens.append(('protected', match.group('protected'), match.group('ptag').lower()))
        elif match.group('comment') is not None:
            comment = match.group('comment')
            if _is_conditional_comment(comment):
                # Условный комментарий ведёт себя как инлайн-узел: пробелы вокруг
                # него оставляем на усмотрение общей логики.
                tokens.append(('conditional', comment, ''))
            # Обычный комментарий просто выбрасываем, соседние текстовые узлы
            # при этом склеиваются логикой ниже (он не попадает в tokens).
        else:
            tag = match.group('tag')
            tokens.append(('tag', tag, _tag_name(tag)))
        pos = match.end()
    if pos < len(html):
        tokens.append(('text', html[pos:], ''))

    # После выброшенных комментариев соседние текстовые узлы могли остаться
    # разорванными - склеиваем, иначе на их стыке вырастет лишний пробел.
    merged: list[tuple[str, str, str]] = []
    for token in tokens:
        if token[0] == 'text' and merged and merged[-1][0] == 'text':
            merged[-1] = ('text', merged[-1][1] + token[1], '')
        else:
            merged.append(token)
    tokens = merged

    def boundary_is_block(index: int) -> bool:
        """True, если по соседству граница документа или блочный тег."""
        if index < 0 or index >= len(tokens):
            return True
        kind, _, name = tokens[index]
        if kind == 'tag':
            return name in _BLOCK_TAGS
        if kind == 'protected':
            # textarea - инлайн-блок, пробел рядом с ним значим.
            return name != 'textarea'
        return False

    out: list[str] = []
    for i, (kind, text, _name) in enumerate(tokens):
        if kind == 'text':
            collapsed = _WS_RE.sub(' ', text)
            if boundary_is_block(i - 1):
                collapsed = collapsed.lstrip(' ')
            if boundary_is_block(i + 1):
                collapsed = collapsed.rstrip(' ')
            out.append(collapsed)
        elif kind == 'tag':
            out.append(_minify_tag(text))
        else:
            out.append(text)
    return ''.join(out)


class HtmlMinifyMiddleware:
    """Минифицирует HTML-ответы: только text/html, статус 200, не админка."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(settings, 'HTML_MINIFY', True):
            return response
        try:
            if getattr(response, 'streaming', False):
                return response
            if response.status_code != 200:
                return response
            if 'text/html' not in response.get('Content-Type', ''):
                return response
            if (request.path or '').startswith('/admin/'):
                return response

            charset = response.charset or 'utf-8'
            original = response.content
            minified = minify_html(original.decode(charset)).encode(charset)
            if len(minified) < len(original):
                response.content = minified
                if response.has_header('Content-Length'):
                    response['Content-Length'] = str(len(minified))
        except Exception:  # noqa: BLE001 - минификация не должна ронять ответ
            logger.exception('HTML minify failed for %s', getattr(request, 'path', '?'))
        return response

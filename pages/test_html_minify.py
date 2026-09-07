"""Тесты минификации HTML на выдаче (config/middleware.py).

Проверяют, что вес ответа падает, но содержимое <pre>/<textarea>/<script>/<style>
остаётся байт в байт, ld+json не ломается, значимый пробел между инлайн-элементами
не исчезает, админка не минифицируется и HTML_MINIFY=0 полностью выключает фичу.
"""
import json
import re

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from config.middleware import minify_html


# Как в pages/test_seo_w37.py: в тестах DEBUG=False и статика идёт через манифест
# WhiteNoise, которого без collectstatic нет.
render_pages = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)


def without_protected_blocks(html: str) -> str:
    """Убирает script/style/pre/textarea: их содержимое минификатор не трогает."""
    return re.sub(
        r"<(pre|textarea|script|style)\b[^>]*>[\s\S]*?</\1\s*>", "", html, flags=re.I
    )


class MinifyFunctionTest(TestCase):
    def test_collapses_indentation_between_blocks(self):
        html = '<div>\n    <p>\n        Привет\n    </p>\n</div>'
        self.assertEqual(minify_html(html), '<div><p>Привет</p></div>')

    def test_pre_content_kept_byte_for_byte(self):
        body = '  строка 1\n\t\tстрока 2\n\n'
        html = '<div>\n  <pre>' + body + '</pre>\n</div>'
        self.assertIn('<pre>' + body + '</pre>', minify_html(html))

    def test_textarea_content_kept_byte_for_byte(self):
        body = '\n  черновик\n     с отступом\n'
        html = '<form>\n  <textarea name="c">' + body + '</textarea>\n</form>'
        self.assertIn('<textarea name="c">' + body + '</textarea>', minify_html(html))

    def test_script_body_kept_byte_for_byte(self):
        body = '\n  var a = 1;\n  //  комментарий  с пробелами\n  var b = "  x  ";\n'
        html = '<body>\n  <script>' + body + '</script>\n</body>'
        self.assertIn('<script>' + body + '</script>', minify_html(html))

    def test_style_body_kept_byte_for_byte(self):
        body = '\n  .a {\n    color: red;\n  }\n'
        html = '<head>\n  <style>' + body + '</style>\n</head>'
        self.assertIn('<style>' + body + '</style>', minify_html(html))

    def test_ld_json_stays_valid_json(self):
        payload = {'@context': 'https://schema.org', '@type': 'FAQPage', 'name': 'Тест  с  пробелами'}
        html = (
            '<head>\n    <script type="application/ld+json">\n'
            + json.dumps(payload, ensure_ascii=False, indent=2)
            + '\n    </script>\n</head>'
        )
        out = minify_html(html)
        raw = out.split('application/ld+json">', 1)[1].split('</script>', 1)[0]
        self.assertEqual(json.loads(raw), payload)

    def test_space_between_inline_elements_survives(self):
        html = '<p>\n  <a href="/a">Раз</a>\n  <a href="/b">Два</a>\n</p>'
        self.assertEqual(minify_html(html), '<p><a href="/a">Раз</a> <a href="/b">Два</a></p>')

    def test_space_inside_paragraph_collapses_to_one(self):
        html = '<p>Купили <b>газон</b>   и   <i>кусты</i> вчера</p>'
        self.assertEqual(minify_html(html), '<p>Купили <b>газон</b> и <i>кусты</i> вчера</p>')

    def test_space_around_button_and_text_survives(self):
        html = '<div>Цена\n  <button>Купить</button>\n  <span>руб</span>\n</div>'
        self.assertEqual(minify_html(html), '<div>Цена <button>Купить</button> <span>руб</span></div>')

    def test_comments_removed_without_gluing_words(self):
        html = '<p>раз <!-- заметка --> два</p>'
        self.assertEqual(minify_html(html), '<p>раз два</p>')

    def test_conditional_comment_kept(self):
        html = '<body>\n<!--[if lt IE 9]><script src="/s.js"></script><![endif]-->\n</body>'
        self.assertIn('<!--[if lt IE 9]><script src="/s.js"></script><![endif]-->', minify_html(html))

    def test_quoted_attribute_value_untouched(self):
        html = '<input value="a  b" data-x="стр  ока">'
        self.assertEqual(minify_html(html), '<input value="a  b" data-x="стр  ока">')

    def test_gt_inside_attribute_does_not_break_parsing(self):
        html = '<meta content="1 > 0">\n<div>\n  текст\n</div>'
        self.assertEqual(minify_html(html), '<meta content="1 > 0"><div>текст</div>')

    def test_attribute_whitespace_collapsed(self):
        html = '<div\n   class="a\n   b"\n   id="x"\n>ок</div>'
        self.assertEqual(minify_html(html), '<div class="a\n   b" id="x">ок</div>')


@render_pages
class MinifyMiddlewareTest(TestCase):
    def test_response_is_minified(self):
        html = self.client.get('/').content.decode()
        self.assertIn('<html', html)
        self.assertNotIn('\n', without_protected_blocks(html))

    @override_settings(HTML_MINIFY=False)
    def test_flag_off_keeps_original_html(self):
        html = self.client.get('/').content.decode()
        self.assertIn('\n    ', without_protected_blocks(html))

    def test_minify_actually_shrinks_page(self):
        with override_settings(HTML_MINIFY=False):
            raw = len(Client().get('/').content)
        small = len(self.client.get('/').content)
        self.assertLess(small, raw)

    def test_admin_is_not_minified(self):
        User.objects.create_superuser('minify_admin', 'a@example.com', 'pass12345')
        self.client.force_login(User.objects.get(username='minify_admin'))
        html = self.client.get('/admin/', follow=True).content.decode()
        self.assertIn('\n', html)

    def test_non_html_response_untouched(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('text/html', response['Content-Type'])

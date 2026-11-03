"""Перелинковка статей /stati/: поле related, обратные ссылки, links[] через API."""
import json

from django.test import Client, TestCase, override_settings

from pages.models import Article

TOKEN = "test-token"

render_pages = override_settings(
    ARTICLE_API_TOKEN=TOKEN,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)


def payload(slug, **extra):
    data = {
        "slug": slug,
        "title": f"Статья {slug}",
        "excerpt": f"Аннотация {slug}",
        "sections": [{"heading": "Раздел", "paragraphs": ["Текст"]}],
        "date_published": "2026-09-01",
        "status": "published",
    }
    data.update(extra)
    return data


@render_pages
class RelatedApiTests(TestCase):
    def post(self, data):
        return Client().post(
            "/api/articles/",
            data=json.dumps(data, ensure_ascii=False),
            content_type="application/json",
            HTTP_X_API_TOKEN=TOKEN,
        )

    def test_related_saved(self):
        resp = self.post(payload("novaya", related=["staraya", "vtoraya"]))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(Article.objects.get(slug="novaya").related, ["staraya", "vtoraya"])
        self.assertEqual(resp.json()["article"]["related"], ["staraya", "vtoraya"])

    def test_related_rejects_self_and_too_many(self):
        self.assertEqual(self.post(payload("a", related=["a"])).status_code, 400)
        self.assertEqual(self.post(payload("a", related=["b", "c", "d", "e"])).status_code, 400)
        self.assertEqual(self.post(payload("a", related=["Плохой"])).status_code, 400)

    def test_links_saved_and_validated(self):
        link = {"before": "Подробнее про ", "anchor": "полив газона", "href": "/stati/poliv/", "after": "."}
        sections = [{"heading": "Раздел", "paragraphs": ["Текст"], "links": [link]}]
        resp = self.post(payload("s-link", sections=sections))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(Article.objects.get(slug="s-link").sections[0]["links"], [link])

        for bad in ("https://evil.ru/", "//evil.ru/", "javascript:alert(1)", "stati/x/"):
            bad_sections = [{"heading": "Р", "paragraphs": ["Т"], "links": [dict(link, href=bad)]}]
            self.assertEqual(self.post(payload("s-bad", sections=bad_sections)).status_code, 400, bad)

    def test_links_only_section_is_valid(self):
        """Секция только со ссылкой (как у link_ukladka_articles) переживает перезаливку."""
        link = {"before": "См. ", "anchor": "укладку", "href": "/ukladka-rulonnogo-gazona/", "after": ""}
        sections = [
            {"heading": "Раздел", "paragraphs": ["Текст"]},
            {"heading": "Ссылка", "links": [link]},
        ]
        self.assertEqual(self.post(payload("s-only", sections=sections)).status_code, 200)

    def test_list_includes_static_articles(self):
        self.post(payload("novaya"))
        data = Client().get("/api/articles/list/", HTTP_X_API_TOKEN=TOKEN).json()
        self.assertIn("excerpt", data["articles"][0])
        static_slugs = {a["slug"] for a in data["static_articles"]}
        self.assertIn("rulonnyy-gazon-v-zharu", static_slugs)


@render_pages
class RelatedRenderTests(TestCase):
    def make(self, slug, **extra):
        fields = payload(slug, **extra)
        fields.pop("slug")
        return Article.objects.create(slug=slug, **fields)

    def html(self, slug):
        resp = Client().get(f"/stati/{slug}/")
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode("utf-8")

    def related_block(self, html):
        start = html.find("data-related-articles")
        if start == -1:
            return ""
        return html[start : html.find("</section>", start)]

    def test_forward_and_backlink(self):
        self.make("staraya")
        self.make("novaya", related=["staraya"])
        self.assertIn('href="/stati/staraya/"', self.related_block(self.html("novaya")))
        # У старой статьи обратная ссылка появилась без перезаливки.
        self.assertIn('href="/stati/novaya/"', self.related_block(self.html("staraya")))

    def test_link_to_static_article(self):
        self.make("novaya", related=["rulonnyy-gazon-v-zharu"])
        self.assertIn('href="/stati/rulonnyy-gazon-v-zharu/"', self.related_block(self.html("novaya")))
        self.assertIn('href="/stati/novaya/"', self.related_block(self.html("rulonnyy-gazon-v-zharu")))

    def test_hidden_articles_not_shown(self):
        self.make("staraya")
        self.make("chernovik", related=["staraya"], status="draft")
        self.make("novaya", related=["net-takoy", "chernovik"])
        self.assertNotIn("/stati/chernovik/", self.related_block(self.html("staraya")))
        self.assertEqual(self.related_block(self.html("novaya")), "")

    def test_no_block_without_related(self):
        self.make("odinokaya")
        self.assertEqual(self.related_block(self.html("odinokaya")), "")


class StaticRelatedMapTests(TestCase):
    def test_static_map_points_to_real_static_keys(self):
        from pages.articles import STATIC_RELATED, static_articles
        from pages.data import STATI_PAGE

        static_slugs = {a["slug"] for a in STATI_PAGE["articles"]}
        self.assertTrue(set(STATIC_RELATED) <= static_slugs)
        for slug, targets in STATIC_RELATED.items():
            self.assertLessEqual(len(targets), 3)
            self.assertNotIn(slug, targets)
            self.assertNotIn("rulonnyy-ili-posevnoy-gazon", targets)
        by_slug = {a["slug"]: a for a in static_articles()}
        self.assertEqual(by_slug["kak-ukladyvat-gazon"]["related"], STATIC_RELATED["kak-ukladyvat-gazon"])


class DuplicateRedirectTests(TestCase):
    def test_duplicate_301_to_factory_version(self):
        resp = Client().get("/stati/rulonnyy-ili-posevnoy-gazon/")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp["Location"], "/stati/rulonnyy-ili-posevnoy-gazon-sibir/")

    def test_duplicate_removed_from_static(self):
        from pages.articles import static_articles

        self.assertNotIn("rulonnyy-ili-posevnoy-gazon", {a["slug"] for a in static_articles()})

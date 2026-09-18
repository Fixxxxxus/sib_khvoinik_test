"""Офлайн-конверсии Метрики: формирование CSV и отметка об отправке.

Сеть не трогаем: requests.post мокается, проверяем ровно то, что уходит в API
и что остаётся в БД после ответа.
"""
from __future__ import annotations

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from pages.models import LandingLead, WholesaleOrder


def _fake_response(status_code=200, payload=None):
    response = mock.Mock()
    response.status_code = status_code
    response.text = "{}"
    response.json.return_value = payload if payload is not None else {
        "uploading": {"id": 42, "status": "UPLOADED"}
    }
    return response


@override_settings(
    YANDEX_METRIKA_ACCESS_TOKEN="test-token",
    YANDEX_METRIKA_COUNTER_ID="108722541",
)
class PushMetrikaConversionsTests(TestCase):
    def setUp(self):
        self.lead = LandingLead.objects.create(
            lead_id="lead-1",
            landing_id="ozelenenie-season-end",
            name="Иван",
            phone="79130000000",
            yclid="1111",
        )
        self.order = WholesaleOrder.objects.create(
            order_id="order-1",
            name="ООО Ромашка",
            phone="79130000001",
            total="150000.00",
            yclid="2222",
        )
        self.no_yclid = LandingLead.objects.create(
            lead_id="lead-2",
            landing_id="ozelenenie-season-end",
            name="Пётр",
            phone="79130000002",
        )

    def _run(self, *args):
        out = StringIO()
        err = StringIO()
        call_command("push_metrika_conversions", *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_dry_run_prints_csv_and_marks_nothing(self):
        with mock.patch("pages.management.commands.push_metrika_conversions.requests.post") as post:
            out, _ = self._run("--dry-run")
        post.assert_not_called()

        lines = [line for line in out.splitlines() if line.strip()]
        self.assertEqual(lines[0], "Yclid,Target,DateTime,Price,Currency")
        self.assertIn(
            f"1111,lead_submit,{int(self.lead.created_at.timestamp())},,", lines[1]
        )
        self.assertIn(
            f"2222,opt_order,{int(self.order.created_at.timestamp())},150000.00,RUB",
            lines[2],
        )
        # Лид без yclid в выгрузку не попадает.
        self.assertNotIn("lead-2", out)

        self.lead.refresh_from_db()
        self.order.refresh_from_db()
        self.assertIsNone(self.lead.metrika_uploaded_at)
        self.assertIsNone(self.order.metrika_uploaded_at)

    def test_successful_upload_marks_records(self):
        with mock.patch(
            "pages.management.commands.push_metrika_conversions.requests.post",
            return_value=_fake_response(),
        ) as post:
            self._run()

        post.assert_called_once()
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["params"], {"client_id_type": "YCLID"})
        self.assertEqual(kwargs["headers"]["Authorization"], "OAuth test-token")
        body = kwargs["files"]["file"][1].decode("utf-8")
        self.assertTrue(body.startswith("Yclid,Target,DateTime,Price,Currency"))
        self.assertIn("2222,opt_order", body)

        self.lead.refresh_from_db()
        self.order.refresh_from_db()
        self.no_yclid.refresh_from_db()
        self.assertIsNotNone(self.lead.metrika_uploaded_at)
        self.assertIsNotNone(self.order.metrika_uploaded_at)
        self.assertIsNone(self.no_yclid.metrika_uploaded_at)

    def test_already_uploaded_is_not_sent_again(self):
        with mock.patch(
            "pages.management.commands.push_metrika_conversions.requests.post",
            return_value=_fake_response(),
        ):
            self._run()
        with mock.patch(
            "pages.management.commands.push_metrika_conversions.requests.post",
            return_value=_fake_response(),
        ) as post:
            out, _ = self._run()
        post.assert_not_called()
        self.assertIn("Нечего отправлять", out)

    def test_api_error_does_not_mark_and_does_not_raise(self):
        bad = _fake_response(status_code=400)
        bad.text = "bad request"
        with mock.patch(
            "pages.management.commands.push_metrika_conversions.requests.post",
            return_value=bad,
        ):
            _, err = self._run()
        self.assertIn("400", err)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.metrika_uploaded_at)

    def test_network_error_does_not_mark_and_does_not_raise(self):
        import requests

        with mock.patch(
            "pages.management.commands.push_metrika_conversions.requests.post",
            side_effect=requests.ConnectionError("boom"),
        ):
            _, err = self._run()
        self.assertIn("недоступна", err)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.metrika_uploaded_at)

    @override_settings(YANDEX_METRIKA_ACCESS_TOKEN="")
    def test_missing_token_exits_quietly(self):
        with mock.patch("pages.management.commands.push_metrika_conversions.requests.post") as post:
            out, _ = self._run()
        post.assert_not_called()
        self.assertIn("YANDEX_METRIKA_ACCESS_TOKEN", out)

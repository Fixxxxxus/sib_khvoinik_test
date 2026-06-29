from django.test import SimpleTestCase
from care_notifications.cards.subscriptions import category_slugs_for_groups


class SubscriptionMapTests(SimpleTestCase):
    def test_maps_group_slugs_to_categories(self):
        self.assertEqual(category_slugs_for_groups(["trees"]), ["derevya"])
        self.assertEqual(
            sorted(category_slugs_for_groups(["trees", "roses", "lawn"])),
            ["derevya", "gazon", "rozy"])

    def test_seasonal_has_no_category(self):
        self.assertEqual(category_slugs_for_groups(["seasonal"]), [])

    def test_unknown_group_ignored(self):
        self.assertEqual(category_slugs_for_groups(["nope"]), [])

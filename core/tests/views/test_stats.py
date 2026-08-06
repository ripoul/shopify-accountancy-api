import datetime
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import make_aware
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Order, Purchase, Royalty, Store, Supplier, Tax

# Fixed reference date for all tests: 2025-05-15
# Current quarter (Q2 2025): 2025-04-01 → 2025-05-15 (44 days elapsed)
# Previous quarter same period (Q1 2025): 2025-01-01 → 2025-02-14
FIXED_TODAY = date(2025, 5, 15)


class BaseStatsViewSetTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="strongpassword",
        )
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )
        self.supplier = Supplier.objects.create(store=self.store, name="Acme")
        assign_perm("can_manage", self.user, self.store)
        self._authenticate(self.user)

    def _authenticate(self, user):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": user.username, "password": "strongpassword"},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def _create_order(
        self,
        processed_at,
        total_price="100.00",
        net_margin="40.00",
        after_tax_result="30.00",
        external_id="gid://shopify/Order/1",
        net_revenue=None,
    ):
        return Order.objects.create(
            store=self.store,
            external_id=external_id,
            name=f"#{external_id[-1]}",
            processed_at=processed_at,
            total_price=Decimal(total_price),
            net_revenue=Decimal(net_revenue if net_revenue is not None else total_price),
            net_margin=Decimal(net_margin),
            after_tax_result=Decimal(after_tax_result),
        )

    def _create_purchase(self, order_date, price="50.00", is_raw_material=False):
        return Purchase.objects.create(
            store=self.store,
            supplier=self.supplier,
            order_date=order_date,
            price=Decimal(price),
            is_raw_material=is_raw_material,
        )


class CurrentQuarterStatsTest(BaseStatsViewSetTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("stat-current-quarter", kwargs={"store_pk": self.store.pk})

    @patch("core.views.stats.timezone")
    def test_returns_200(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("core.views.stats.timezone")
    def test_store_without_permission_returns_403(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        other_store = Store.objects.create(
            shop_domain="other.myshopify.com",
            name="Other",
            access_token="shpat_other",
        )
        url = reverse("stat-current-quarter", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("core.views.stats.timezone")
    def test_response_contains_both_periods(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        response = self.client.get(self.url)
        self.assertIn("current_quarter", response.data)
        self.assertIn("previous_quarter", response.data)

    @patch("core.views.stats.timezone")
    def test_response_fields_present(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        response = self.client.get(self.url)
        expected_fields = {
            "period",
            "start_date",
            "end_date",
            "revenue",
            "profit_before_tax",
            "profit_after_tax",
            "profit_after_tax_after_purchase",
            "cash_variation",
            "order_count",
            "average_profit_per_order",
            "average_basket",
        }
        self.assertEqual(set(response.data["current_quarter"].keys()), expected_fields)
        self.assertEqual(set(response.data["previous_quarter"].keys()), expected_fields)

    @patch("core.views.stats.timezone")
    def test_zero_orders_returns_zeros(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        response = self.client.get(self.url)
        current = response.data["current_quarter"]
        self.assertEqual(current["revenue"], "0.00")
        self.assertEqual(current["profit_before_tax"], "0.00")
        self.assertEqual(current["profit_after_tax"], "0.00")
        self.assertEqual(current["profit_after_tax_after_purchase"], "0.00")
        self.assertEqual(current["cash_variation"], "0.00")
        self.assertEqual(current["order_count"], 0)
        self.assertEqual(current["average_profit_per_order"], "0.00")
        self.assertEqual(current["average_basket"], "0.00")

    @patch("core.views.stats.timezone")
    def test_current_quarter_period_and_dates(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        response = self.client.get(self.url)
        current = response.data["current_quarter"]
        self.assertEqual(current["period"], "2025/02")
        self.assertEqual(current["start_date"], "2025-04-01")
        self.assertEqual(current["end_date"], "2025-05-15")

    @patch("core.views.stats.timezone")
    def test_previous_quarter_period_and_dates(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        response = self.client.get(self.url)
        prev = response.data["previous_quarter"]
        self.assertEqual(prev["period"], "2025/01")
        self.assertEqual(prev["start_date"], "2025-01-01")
        self.assertEqual(prev["end_date"], "2025-02-14")

    @patch("core.views.stats.timezone")
    def test_current_quarter_revenue(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            total_price="100.00",
            external_id="gid://shopify/Order/1",
        )
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 5, 1)),
            total_price="200.00",
            external_id="gid://shopify/Order/2",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data["current_quarter"]["revenue"], "300.00")

    @patch("core.views.stats.timezone")
    def test_current_quarter_revenue_reflects_net_revenue_with_returns(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            total_price="100.00",
            net_revenue="70.00",
            external_id="gid://shopify/Order/1",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data["current_quarter"]["revenue"], "70.00")

    @patch("core.views.stats.timezone")
    def test_current_quarter_order_count(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            external_id="gid://shopify/Order/1",
        )
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 5, 1)),
            external_id="gid://shopify/Order/2",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data["current_quarter"]["order_count"], 2)

    @patch("core.views.stats.timezone")
    def test_current_quarter_profit_metrics(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            net_margin="40.00",
            after_tax_result="30.00",
            external_id="gid://shopify/Order/1",
        )
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 5, 1)),
            net_margin="80.00",
            after_tax_result="60.00",
            external_id="gid://shopify/Order/2",
        )
        response = self.client.get(self.url)
        current = response.data["current_quarter"]
        self.assertEqual(current["profit_before_tax"], "120.00")
        self.assertEqual(current["profit_after_tax"], "90.00")

    @patch("core.views.stats.timezone")
    def test_current_quarter_average_basket(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            total_price="100.00",
            external_id="gid://shopify/Order/1",
        )
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 5, 1)),
            total_price="200.00",
            external_id="gid://shopify/Order/2",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data["current_quarter"]["average_basket"], "150.00")

    @patch("core.views.stats.timezone")
    def test_current_quarter_average_profit_per_order(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            after_tax_result="30.00",
            external_id="gid://shopify/Order/1",
        )
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 5, 1)),
            after_tax_result="60.00",
            external_id="gid://shopify/Order/2",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data["current_quarter"]["average_profit_per_order"], "45.00")

    @patch("core.views.stats.timezone")
    def test_orders_outside_current_quarter_excluded(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        # Q4 2024 — excluded
        self._create_order(
            processed_at=make_aware(datetime.datetime(2024, 12, 1)),
            total_price="500.00",
            external_id="gid://shopify/Order/old",
        )
        # After today — excluded
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 5, 16)),
            total_price="500.00",
            external_id="gid://shopify/Order/future",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data["current_quarter"]["order_count"], 0)
        self.assertEqual(response.data["current_quarter"]["revenue"], "0.00")

    @patch("core.views.stats.timezone")
    def test_purchases_deducted_from_profit_after_purchase(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 20)),
            after_tax_result="90.00",
            external_id="gid://shopify/Order/1",
        )
        self._create_purchase(order_date=date(2025, 4, 25), price="25.00")
        response = self.client.get(self.url)
        current = response.data["current_quarter"]
        self.assertEqual(current["profit_after_tax"], "90.00")
        self.assertEqual(current["profit_after_tax_after_purchase"], "65.00")

    @patch("core.views.stats.timezone")
    def test_purchases_outside_period_not_deducted(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 20)),
            after_tax_result="90.00",
            external_id="gid://shopify/Order/1",
        )
        # Purchase in Q1 2025 — should not affect current quarter
        self._create_purchase(order_date=date(2025, 3, 1), price="25.00")
        response = self.client.get(self.url)
        self.assertEqual(response.data["current_quarter"]["profit_after_tax_after_purchase"], "90.00")

    @patch("core.views.stats.timezone")
    def test_previous_quarter_includes_orders_within_cutoff(self, mock_tz):
        # Previous period: 2025-01-01 to 2025-02-14
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 2, 10)),
            total_price="100.00",
            external_id="gid://shopify/Order/prev1",
        )
        response = self.client.get(self.url)
        prev = response.data["previous_quarter"]
        self.assertEqual(prev["order_count"], 1)
        self.assertEqual(prev["revenue"], "100.00")

    @patch("core.views.stats.timezone")
    def test_previous_quarter_excludes_orders_after_cutoff(self, mock_tz):
        # 2025-03-01 is in Q1 2025 but after the cutoff (2025-02-14) — excluded
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 3, 1)),
            total_price="200.00",
            external_id="gid://shopify/Order/after_cutoff",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data["previous_quarter"]["order_count"], 0)

    @patch("core.views.stats.timezone")
    def test_previous_quarter_purchases_deducted(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 1, 20)),
            after_tax_result="80.00",
            external_id="gid://shopify/Order/prev1",
        )
        self._create_purchase(order_date=date(2025, 1, 25), price="30.00")
        response = self.client.get(self.url)
        prev = response.data["previous_quarter"]
        self.assertEqual(prev["profit_after_tax"], "80.00")
        self.assertEqual(prev["profit_after_tax_after_purchase"], "50.00")

    @patch("core.views.stats.timezone")
    def test_q1_previous_quarter_is_q4_of_previous_year(self, mock_tz):
        # today = 2025-02-15 (Q1 2025)
        # days_elapsed = 45, prev = Q4 2024: 2024-10-01 to 2024-11-15
        mock_tz.localdate.return_value = date(2025, 2, 15)
        response = self.client.get(self.url)
        prev = response.data["previous_quarter"]
        self.assertEqual(prev["period"], "2024/04")
        self.assertEqual(prev["start_date"], "2024-10-01")
        self.assertEqual(prev["end_date"], "2024-11-15")

    @patch("core.views.stats.timezone")
    def test_cash_variation_is_revenue_minus_all_purchases(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 20)),
            total_price="100.00",
            after_tax_result="70.00",
            external_id="gid://shopify/Order/1",
        )
        self._create_purchase(order_date=date(2025, 4, 25), price="20.00", is_raw_material=False)
        self._create_purchase(order_date=date(2025, 4, 26), price="15.00", is_raw_material=True)
        response = self.client.get(self.url)
        current = response.data["current_quarter"]
        # cash_variation = CA - all purchases = 100 - 20 - 15 = 65
        self.assertEqual(current["cash_variation"], "65.00")
        # profit_after_tax_after_purchase excludes raw material = 70 - 20 = 50
        self.assertEqual(current["profit_after_tax_after_purchase"], "50.00")

    @patch("core.views.stats.timezone")
    def test_cash_variation_no_purchases(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 20)),
            total_price="100.00",
            after_tax_result="70.00",
            external_id="gid://shopify/Order/1",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data["current_quarter"]["cash_variation"], "100.00")

    @patch("core.views.stats.timezone")
    def test_raw_material_purchases_not_deducted(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 20)),
            after_tax_result="90.00",
            external_id="gid://shopify/Order/1",
        )
        self._create_purchase(order_date=date(2025, 4, 25), price="25.00", is_raw_material=True)
        response = self.client.get(self.url)
        current = response.data["current_quarter"]
        self.assertEqual(current["profit_after_tax"], "90.00")
        self.assertEqual(current["profit_after_tax_after_purchase"], "90.00")

    @patch("core.views.stats.timezone")
    def test_only_non_raw_material_purchases_deducted(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 20)),
            after_tax_result="90.00",
            external_id="gid://shopify/Order/1",
        )
        self._create_purchase(order_date=date(2025, 4, 25), price="20.00", is_raw_material=False)
        self._create_purchase(order_date=date(2025, 4, 26), price="15.00", is_raw_material=True)
        response = self.client.get(self.url)
        current = response.data["current_quarter"]
        self.assertEqual(current["profit_after_tax_after_purchase"], "70.00")

    @patch("core.views.stats.timezone")
    def test_store_isolation(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        other_store = Store.objects.create(
            shop_domain="other.myshopify.com",
            name="Other",
            access_token="shpat_other",
        )
        # Order belonging to another store — should not appear in our stats
        Order.objects.create(
            store=other_store,
            external_id="gid://shopify/Order/other",
            name="#9999",
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            total_price=Decimal("999.00"),
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data["current_quarter"]["order_count"], 0)
        self.assertEqual(response.data["current_quarter"]["revenue"], "0.00")


# Fixed reference date: 2025-05-15 (Q2 2025 in progress)
# Q1 2025: 2025-01-01 → 2025-03-31
# Q2 2025: 2025-04-01 → 2025-05-15 (today, is_current=True)
class QuartersHistoryTest(BaseStatsViewSetTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("stat-quarters-history", kwargs={"store_pk": self.store.pk})

    @patch("core.views.stats.timezone")
    def test_no_orders_returns_empty_list(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("core.views.stats.timezone")
    def test_no_permission_returns_403(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        other_store = Store.objects.create(
            shop_domain="other.myshopify.com",
            name="Other",
            access_token="shpat_other",
        )
        url = reverse("stat-quarters-history", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("core.views.stats.timezone")
    def test_single_quarter_returns_one_item(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            total_price="100.00",
            external_id="gid://shopify/Order/1",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    @patch("core.views.stats.timezone")
    def test_response_fields_present(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            external_id="gid://shopify/Order/1",
        )
        response = self.client.get(self.url)
        expected_fields = {
            "period",
            "start_date",
            "end_date",
            "is_current",
            "revenue",
            "profit_before_tax",
            "profit_after_tax",
            "profit_after_tax_after_purchase",
            "cash_variation",
            "order_count",
            "average_profit_per_order",
            "average_basket",
        }
        self.assertEqual(set(response.data[0].keys()), expected_fields)

    @patch("core.views.stats.timezone")
    def test_current_quarter_marked_is_current(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            external_id="gid://shopify/Order/1",
        )
        response = self.client.get(self.url)
        last = response.data[-1]
        self.assertTrue(last["is_current"])
        self.assertEqual(last["end_date"], str(FIXED_TODAY))

    @patch("core.views.stats.timezone")
    def test_multiple_quarters_ordered_chronologically(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        # Orders in Q4 2024 and Q2 2025
        self._create_order(
            processed_at=make_aware(datetime.datetime(2024, 11, 1)),
            total_price="50.00",
            external_id="gid://shopify/Order/q4",
        )
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            total_price="100.00",
            external_id="gid://shopify/Order/q2",
        )
        response = self.client.get(self.url)
        periods = [item["period"] for item in response.data]
        # Q4 2024, Q1 2025 (no data), Q2 2025
        self.assertEqual(periods[0], "2024/04")
        self.assertEqual(periods[-1], "2025/02")
        # Quarters are in ascending order
        self.assertEqual(periods, sorted(periods))

    @patch("core.views.stats.timezone")
    def test_empty_quarters_between_data_are_included(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        # Q4 2024 has data, Q1 2025 has none, Q2 2025 is current
        self._create_order(
            processed_at=make_aware(datetime.datetime(2024, 11, 1)),
            total_price="50.00",
            external_id="gid://shopify/Order/q4",
        )
        response = self.client.get(self.url)
        self.assertEqual(len(response.data), 3)
        # Q1 2025 is in between and should have 0 revenue
        q1_item = next(item for item in response.data if item["period"] == "2025/01")
        self.assertEqual(q1_item["revenue"], "0.00")
        self.assertFalse(q1_item["is_current"])

    @patch("core.views.stats.timezone")
    def test_complete_quarter_uses_calendar_end_date(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 1, 15)),
            external_id="gid://shopify/Order/1",
        )
        response = self.client.get(self.url)
        q1_item = next(item for item in response.data if item["period"] == "2025/01")
        self.assertEqual(q1_item["start_date"], "2025-01-01")
        self.assertEqual(q1_item["end_date"], "2025-03-31")
        self.assertFalse(q1_item["is_current"])

    @patch("core.views.stats.timezone")
    def test_capped_at_20_most_recent_quarters(self, mock_tz):
        # today = 2026-06-15 → Q2 2026
        # 25 quarters back → Q1 2020
        # We should only get 20 quarters (Q3 2021 → Q2 2026)
        mock_tz.localdate.return_value = date(2026, 6, 15)
        # Create one order in Q1 2020 (25 quarters ago)
        Order.objects.create(
            store=self.store,
            external_id="gid://shopify/Order/old",
            name="#old",
            processed_at=make_aware(datetime.datetime(2020, 1, 10)),
            total_price=Decimal("10.00"),
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 20)
        # Oldest returned quarter must be Q3 2021 (20 quarters before Q2 2026)
        self.assertEqual(response.data[0]["period"], "2021/03")
        # Most recent must be current quarter Q2 2026
        self.assertEqual(response.data[-1]["period"], "2026/02")
        self.assertTrue(response.data[-1]["is_current"])

    @patch("core.views.stats.timezone")
    def test_revenue_aggregated_correctly_per_quarter(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 1, 10)),
            total_price="200.00",
            external_id="gid://shopify/Order/q1a",
        )
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 2, 20)),
            total_price="100.00",
            external_id="gid://shopify/Order/q1b",
        )
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 5)),
            total_price="50.00",
            external_id="gid://shopify/Order/q2",
        )
        response = self.client.get(self.url)
        q1_item = next(item for item in response.data if item["period"] == "2025/01")
        q2_item = next(item for item in response.data if item["period"] == "2025/02")
        self.assertEqual(q1_item["revenue"], "300.00")
        self.assertEqual(q2_item["revenue"], "50.00")

    @patch("core.views.stats.timezone")
    def test_store_isolation(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        other_store = Store.objects.create(
            shop_domain="other.myshopify.com",
            name="Other",
            access_token="shpat_other",
        )
        Order.objects.create(
            store=other_store,
            external_id="gid://shopify/Order/other",
            name="#9999",
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            total_price=Decimal("999.00"),
        )
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            total_price="10.00",
            external_id="gid://shopify/Order/mine",
        )
        response = self.client.get(self.url)
        q2_item = next(item for item in response.data if item["period"] == "2025/02")
        self.assertEqual(q2_item["revenue"], "10.00")

    @patch("core.views.stats.timezone")
    def test_q4_calendar_end_date(self, mock_tz):
        # Q4 ends on Dec 31
        mock_tz.localdate.return_value = date(2025, 2, 1)
        self._create_order(
            processed_at=make_aware(datetime.datetime(2024, 10, 10)),
            external_id="gid://shopify/Order/q4",
        )
        response = self.client.get(self.url)
        q4_item = next(item for item in response.data if item["period"] == "2024/04")
        self.assertEqual(q4_item["end_date"], "2024-12-31")

    @patch("core.views.stats.timezone")
    def test_q2_calendar_end_date(self, mock_tz):
        # Q2 ends on Jun 30
        mock_tz.localdate.return_value = date(2025, 8, 1)
        self._create_order(
            processed_at=make_aware(datetime.datetime(2025, 4, 10)),
            external_id="gid://shopify/Order/q2",
        )
        response = self.client.get(self.url)
        q2_item = next(item for item in response.data if item["period"] == "2025/02")
        self.assertEqual(q2_item["end_date"], "2025-06-30")


class TreasuryStatsTest(BaseStatsViewSetTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("stat-treasury", kwargs={"store_pk": self.store.pk})

    def _create_tax(self, quarter="2024/01", amount="100.00", payment_date=None):
        return Tax.objects.create(store=self.store, quarter=quarter, amount=Decimal(amount), payment_date=payment_date)

    def _create_royalty(self, quarter="2024/01", amount="50.00", payment_date=None):
        return Royalty.objects.create(
            store=self.store, quarter=quarter, amount=Decimal(amount), payment_date=payment_date
        )

    def test_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_403(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("stat-treasury", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_response_fields_present(self):
        response = self.client.get(self.url)
        expected_fields = {
            "bank_amount",
            "cash_amount",
            "unpaid_taxes_amount",
            "unpaid_royalties_amount",
            "fixed_costs_reserve",
            "investable_amount",
        }
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_bank_and_cash_amounts_reflect_store(self):
        self.store.bank_amount = Decimal("10000.00")
        self.store.cash_amount = Decimal("250.00")
        self.store.save()
        response = self.client.get(self.url)
        self.assertEqual(response.data["bank_amount"], "10000.00")
        self.assertEqual(response.data["cash_amount"], "250.00")

    def test_zero_state_returns_zeros(self):
        response = self.client.get(self.url)
        self.assertEqual(response.data["bank_amount"], "0.00")
        self.assertEqual(response.data["cash_amount"], "0.00")
        self.assertEqual(response.data["unpaid_taxes_amount"], "0.00")
        self.assertEqual(response.data["unpaid_royalties_amount"], "0.00")
        self.assertEqual(response.data["fixed_costs_reserve"], "0.00")
        self.assertEqual(response.data["investable_amount"], "0.00")

    def test_unpaid_taxes_are_summed(self):
        self._create_tax(quarter="2024/01", amount="100.00")
        self._create_tax(quarter="2024/02", amount="150.00")
        response = self.client.get(self.url)
        self.assertEqual(response.data["unpaid_taxes_amount"], "250.00")

    def test_paid_taxes_are_excluded(self):
        self._create_tax(quarter="2024/01", amount="100.00", payment_date=date(2024, 4, 30))
        self._create_tax(quarter="2024/02", amount="150.00")
        response = self.client.get(self.url)
        self.assertEqual(response.data["unpaid_taxes_amount"], "150.00")

    def test_unpaid_royalties_are_summed(self):
        self._create_royalty(quarter="2024/01", amount="30.00")
        self._create_royalty(quarter="2024/02", amount="45.00")
        response = self.client.get(self.url)
        self.assertEqual(response.data["unpaid_royalties_amount"], "75.00")

    def test_paid_royalties_are_excluded(self):
        self._create_royalty(quarter="2024/01", amount="30.00", payment_date=date(2024, 4, 30))
        self._create_royalty(quarter="2024/02", amount="45.00")
        response = self.client.get(self.url)
        self.assertEqual(response.data["unpaid_royalties_amount"], "45.00")

    def test_fixed_costs_reserve_reflects_store_value(self):
        self.store.fixed_costs_reserve = Decimal("3000.00")
        self.store.save()
        response = self.client.get(self.url)
        self.assertEqual(response.data["fixed_costs_reserve"], "3000.00")

    def test_investable_amount_computed_correctly(self):
        self.store.bank_amount = Decimal("10000.00")
        self.store.fixed_costs_reserve = Decimal("3000.00")
        self.store.save()
        # Saving a Tax auto-recalculates the Royalty for the same quarter (see
        # core/signals/royalty.py), so use a different quarter to avoid a unique_together clash.
        self._create_tax(quarter="2024/01", amount="500.00")
        self._create_royalty(quarter="2024/02", amount="200.00")
        response = self.client.get(self.url)
        # 10000 - 500 - 200 - 3000 = 6300
        self.assertEqual(response.data["investable_amount"], "6300.00")

    def test_investable_amount_can_be_negative(self):
        self.store.bank_amount = Decimal("1000.00")
        self.store.fixed_costs_reserve = Decimal("3000.00")
        self.store.save()
        self._create_tax(quarter="2024/01", amount="500.00")
        response = self.client.get(self.url)
        # 1000 - 500 - 0 - 3000 = -2500
        self.assertEqual(response.data["investable_amount"], "-2500.00")

    def test_store_isolation(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        other_store.bank_amount = Decimal("99999.00")
        other_store.save()
        Tax.objects.create(store=other_store, quarter="2024/01", amount=Decimal("999.00"))
        Royalty.objects.create(store=other_store, quarter="2024/02", amount=Decimal("999.00"))

        self.store.bank_amount = Decimal("1000.00")
        self.store.save()
        self._create_tax(quarter="2024/01", amount="100.00")

        response = self.client.get(self.url)
        self.assertEqual(response.data["bank_amount"], "1000.00")
        self.assertEqual(response.data["unpaid_taxes_amount"], "100.00")
        self.assertEqual(response.data["unpaid_royalties_amount"], "0.00")

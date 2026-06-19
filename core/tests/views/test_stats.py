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

from core.models import Order, Purchase, Store, Supplier

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
    ):
        return Order.objects.create(
            store=self.store,
            external_id=external_id,
            name=f"#{external_id[-1]}",
            processed_at=processed_at,
            total_price=Decimal(total_price),
            net_margin=Decimal(net_margin),
            after_tax_result=Decimal(after_tax_result),
        )

    def _create_purchase(self, order_date, price="50.00"):
        return Purchase.objects.create(
            store=self.store,
            supplier=self.supplier,
            order_date=order_date,
            price=Decimal(price),
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
    def test_store_without_permission_returns_404(self, mock_tz):
        mock_tz.localdate.return_value = FIXED_TODAY
        other_store = Store.objects.create(
            shop_domain="other.myshopify.com",
            name="Other",
            access_token="shpat_other",
        )
        url = reverse("stat-current-quarter", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

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

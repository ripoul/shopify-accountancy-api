import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import make_aware
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Order, OrderExpense, OrderLineItem, Store


class BaseOrderViewSetTestCase(TestCase):
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
        name="#1001",
        external_id="gid://shopify/Order/1",
        total_price="29.99",
        processed_at=None,
        quarter="2024/01",
    ):
        return Order.objects.create(
            store=self.store,
            external_id=external_id,
            name=name,
            processed_at=processed_at or make_aware(datetime.datetime(2024, 3, 15, 10, 0, 0)),
            total_price=Decimal(total_price),
            quarter=quarter,
        )


class OrderViewSetListTest(BaseOrderViewSetTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("order-list", kwargs={"store_pk": self.store.pk})

    def test_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("order-list", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_orders_for_store(self):
        self._create_order(name="#1001")
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "#1001")

    def test_does_not_return_other_store_orders(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        Order.objects.create(
            store=other_store,
            external_id="gid://shopify/Order/99",
            name="#9999",
            processed_at=make_aware(datetime.datetime(2024, 1, 1)),
        )
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_ordered_by_processed_at_desc(self):
        self._create_order(
            name="#1001",
            external_id="gid://shopify/Order/1",
            processed_at=make_aware(datetime.datetime(2024, 1, 1)),
        )
        self._create_order(
            name="#1002",
            external_id="gid://shopify/Order/2",
            processed_at=make_aware(datetime.datetime(2024, 6, 1)),
        )
        response = self.client.get(self.url)
        names = [r["name"] for r in response.data["results"]]
        self.assertEqual(names, ["#1002", "#1001"])

    def test_filter_by_name(self):
        self._create_order(name="#1001", external_id="gid://shopify/Order/1")
        self._create_order(name="#2000", external_id="gid://shopify/Order/2")
        response = self.client.get(self.url, {"name": "100"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "#1001")

    def test_filter_by_name_case_insensitive(self):
        self._create_order(name="#ABC", external_id="gid://shopify/Order/1")
        self._create_order(name="#XYZ", external_id="gid://shopify/Order/2")
        response = self.client.get(self.url, {"name": "abc"})
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_by_quarter(self):
        self._create_order(
            name="#1001",
            external_id="gid://shopify/Order/1",
            quarter="2024/01",
        )
        self._create_order(
            name="#1002",
            external_id="gid://shopify/Order/2",
            quarter="2024/02",
        )
        response = self.client.get(self.url, {"quarter": "2024/01"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "#1001")

    def test_filter_by_processed_after(self):
        self._create_order(
            name="#1001",
            external_id="gid://shopify/Order/1",
            processed_at=make_aware(datetime.datetime(2024, 1, 1)),
        )
        self._create_order(
            name="#1002",
            external_id="gid://shopify/Order/2",
            processed_at=make_aware(datetime.datetime(2024, 6, 1)),
        )
        response = self.client.get(self.url, {"processed_after": "2024-03-01T00:00:00Z"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "#1002")

    def test_filter_by_processed_before(self):
        self._create_order(
            name="#1001",
            external_id="gid://shopify/Order/1",
            processed_at=make_aware(datetime.datetime(2024, 1, 1)),
        )
        self._create_order(
            name="#1002",
            external_id="gid://shopify/Order/2",
            processed_at=make_aware(datetime.datetime(2024, 6, 1)),
        )
        response = self.client.get(self.url, {"processed_before": "2024-03-01T00:00:00Z"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "#1001")

    def test_ordering_by_total_price_asc(self):
        self._create_order(name="#cheap", external_id="gid://shopify/Order/1", total_price="10.00")
        self._create_order(name="#expensive", external_id="gid://shopify/Order/2", total_price="100.00")
        response = self.client.get(self.url, {"ordering": "total_price"})
        names = [r["name"] for r in response.data["results"]]
        self.assertEqual(names[0], "#cheap")

    def test_ordering_by_total_price_desc(self):
        self._create_order(name="#cheap", external_id="gid://shopify/Order/1", total_price="10.00")
        self._create_order(name="#expensive", external_id="gid://shopify/Order/2", total_price="100.00")
        response = self.client.get(self.url, {"ordering": "-total_price"})
        names = [r["name"] for r in response.data["results"]]
        self.assertEqual(names[0], "#expensive")

    def test_response_includes_nested_line_items(self):
        self._create_order()
        response = self.client.get(self.url)
        self.assertIn("line_items", response.data["results"][0])

    def test_response_includes_nested_expenses(self):
        self._create_order()
        response = self.client.get(self.url)
        self.assertIn("expenses", response.data["results"][0])

    def test_response_includes_nested_discounts(self):
        self._create_order()
        response = self.client.get(self.url)
        self.assertIn("discounts", response.data["results"][0])


class OrderViewSetImportTest(BaseOrderViewSetTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("order-import-orders", kwargs={"store_pk": self.store.pk})

    @patch("core.views.order.upsert_orders")
    def test_import_returns_204(self, _mock):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @patch("core.views.order.upsert_orders")
    def test_import_with_no_orders_calls_with_since_none(self, mock_upsert):
        self.client.post(self.url)
        mock_upsert.assert_called_once_with(self.store, since=None)

    @patch("core.views.order.upsert_orders")
    def test_import_uses_last_order_processed_at_as_since(self, mock_upsert):
        processed_at = make_aware(datetime.datetime(2024, 6, 1, 12, 0, 0))
        self._create_order(processed_at=processed_at)

        self.client.post(self.url)

        mock_upsert.assert_called_once_with(self.store, since=processed_at)

    @patch("core.views.order.upsert_orders")
    def test_import_with_external_id(self, mock_upsert):
        response = self.client.post(self.url, {"external_id": "gid://shopify/Order/42"})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        mock_upsert.assert_called_once_with(self.store, external_id="gid://shopify/Order/42")

    def test_import_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_import_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("order-import-orders", kwargs={"store_pk": other_store.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class OrderExpenseViewSetTest(BaseOrderViewSetTestCase):
    def setUp(self):
        super().setUp()
        self.order = self._create_order()
        self.list_url = reverse(
            "order-expense-list",
            kwargs={"store_pk": self.store.pk, "order_pk": self.order.pk},
        )

    def _expense_detail_url(self, expense):
        return reverse(
            "order-expense-detail",
            kwargs={"store_pk": self.store.pk, "order_pk": self.order.pk, "expense_pk": expense.pk},
        )

    def _create_manual_expense(self, amount="5.00", expense_type=OrderExpense.Type.DELIVERY):
        return OrderExpense.objects.create(
            order=self.order,
            type=expense_type,
            source=OrderExpense.Source.MANUAL,
            amount=Decimal(amount),
            label="Test expense",
        )

    def test_list_returns_200(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_only_returns_manual_expenses(self):
        self._create_manual_expense()
        OrderExpense.objects.create(
            order=self.order,
            type=OrderExpense.Type.SHOPIFY_PAYMENT,
            source=OrderExpense.Source.AUTO,
            amount=Decimal("1.00"),
        )

        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["source"], "MANUAL")

    def test_create_expense_returns_201(self):
        response = self.client.post(self.list_url, {"type": "DELIVERY", "amount": "5.00", "label": "Shipping"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_expense_sets_manual_source(self):
        self.client.post(self.list_url, {"type": "DELIVERY", "amount": "5.00", "label": "Shipping"})

        expense = OrderExpense.objects.get(order=self.order, type=OrderExpense.Type.DELIVERY)
        self.assertEqual(expense.source, OrderExpense.Source.MANUAL)

    def test_create_shopify_payment_type_rejected(self):
        response = self.client.post(self.list_url, {"type": "SHOPIFY_PAYMENT", "amount": "1.00", "label": "Fee"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_expense_triggers_recompute(self):
        with patch.object(Order, "recompute_financials") as mock_recompute:
            self.client.post(self.list_url, {"type": "DELIVERY", "amount": "5.00", "label": "Shipping"})
            mock_recompute.assert_called_once()

    def test_update_expense_returns_200(self):
        expense = self._create_manual_expense()
        response = self.client.patch(self._expense_detail_url(expense), {"amount": "10.00"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_expense_triggers_recompute(self):
        expense = self._create_manual_expense()
        with patch.object(Order, "recompute_financials") as mock_recompute:
            self.client.patch(self._expense_detail_url(expense), {"amount": "10.00"})
            mock_recompute.assert_called_once()

    def test_delete_expense_returns_204(self):
        expense = self._create_manual_expense()
        response = self.client.delete(self._expense_detail_url(expense))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_expense_triggers_recompute(self):
        expense = self._create_manual_expense()
        with patch.object(Order, "recompute_financials") as mock_recompute:
            self.client.delete(self._expense_detail_url(expense))
            mock_recompute.assert_called_once()

    def test_delete_expense_removes_it(self):
        expense = self._create_manual_expense()
        self.client.delete(self._expense_detail_url(expense))
        self.assertFalse(OrderExpense.objects.filter(pk=expense.pk).exists())

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse(
            "order-expense-list",
            kwargs={"store_pk": other_store.pk, "order_pk": self.order.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class OrderLineItemViewSetTest(BaseOrderViewSetTestCase):
    def setUp(self):
        super().setUp()
        self.order = self._create_order()
        self.line_item = OrderLineItem.objects.create(
            order=self.order,
            external_id="gid://shopify/LineItem/1",
            title="Test Product",
            quantity=2,
            unit_price=Decimal("14.99"),
            distributor_price=Decimal("8.00"),
        )

    def _detail_url(self, line_item=None):
        item = line_item or self.line_item
        return reverse(
            "order-line-item-detail",
            kwargs={"store_pk": self.store.pk, "order_pk": self.order.pk, "line_item_pk": item.pk},
        )

    def test_retrieve_returns_200(self):
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_returns_correct_data(self):
        response = self.client.get(self._detail_url())
        self.assertEqual(response.data["title"], "Test Product")
        self.assertEqual(response.data["quantity"], 2)
        self.assertEqual(Decimal(response.data["distributor_price"]), Decimal("8.00"))

    def test_retrieve_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse(
            "order-line-item-detail",
            kwargs={"store_pk": other_store.pk, "order_pk": self.order.pk, "line_item_pk": self.line_item.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_wrong_order_returns_404(self):
        other_order = self._create_order(name="#9999", external_id="gid://shopify/Order/9")
        url = reverse(
            "order-line-item-detail",
            kwargs={"store_pk": self.store.pk, "order_pk": other_order.pk, "line_item_pk": self.line_item.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_distributor_price_returns_200(self):
        response = self.client.patch(self._detail_url(), {"distributor_price": "12.50"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_patch_distributor_price_updates_value(self):
        self.client.patch(self._detail_url(), {"distributor_price": "12.50"})
        self.line_item.refresh_from_db()
        self.assertEqual(self.line_item.distributor_price, Decimal("12.50"))

    def test_patch_triggers_recompute_financials(self):
        with patch.object(Order, "recompute_financials") as mock_recompute:
            self.client.patch(self._detail_url(), {"distributor_price": "12.50"})
            mock_recompute.assert_called_once()

    def test_patch_read_only_field_is_ignored(self):
        self.client.patch(self._detail_url(), {"title": "Hacked", "distributor_price": "5.00"})
        self.line_item.refresh_from_db()
        self.assertEqual(self.line_item.title, "Test Product")

    def test_patch_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.patch(self._detail_url(), {"distributor_price": "12.50"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other2.myshopify.com", name="Other2", access_token="shpat_o2")
        url = reverse(
            "order-line-item-detail",
            kwargs={"store_pk": other_store.pk, "order_pk": self.order.pk, "line_item_pk": self.line_item.pk},
        )
        response = self.client.patch(url, {"distributor_price": "12.50"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

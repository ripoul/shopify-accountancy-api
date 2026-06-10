from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Purchase, Store, Supplier


class BasePurchaseViewSetTestCase(TestCase):
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

    def _create_purchase(
        self, supplier=None, order_date=date(2026, 1, 15), price="120.50", order_number="", store=None
    ):
        return Purchase.objects.create(
            store=store or self.store,
            supplier=supplier or self.supplier,
            order_date=order_date,
            price=price,
            order_number=order_number,
        )


class PurchaseViewSetTest(BasePurchaseViewSetTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("purchase-list", kwargs={"store_pk": self.store.pk})

    def test_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("purchase-list", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_purchases_for_store(self):
        self._create_purchase()
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["supplier"], self.supplier.pk)

    def test_does_not_return_other_store_purchases(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        other_supplier = Supplier.objects.create(store=other_store, name="Other Supplier")
        Purchase.objects.create(store=other_store, supplier=other_supplier, order_date=date(2026, 1, 1), price="10.00")
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_create_assigns_store(self):
        response = self.client.post(
            self.url,
            {"supplier": self.supplier.pk, "order_date": "2026-02-01", "price": "99.90"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        purchase = Purchase.objects.get(pk=response.data["id"])
        self.assertEqual(purchase.store, self.store)
        self.assertEqual(purchase.supplier, self.supplier)

    def test_create_rejects_supplier_from_other_store(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        other_supplier = Supplier.objects.create(store=other_store, name="Other Supplier")
        response = self.client.post(
            self.url,
            {"supplier": other_supplier.pk, "order_date": "2026-02-01", "price": "99.90"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_ignores_store_in_payload(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        response = self.client.post(
            self.url,
            {"supplier": self.supplier.pk, "order_date": "2026-02-01", "price": "99.90", "store": other_store.pk},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        purchase = Purchase.objects.get(pk=response.data["id"])
        self.assertEqual(purchase.store, self.store)

    def test_retrieve_returns_purchase(self):
        purchase = self._create_purchase()
        url = reverse("purchase-detail", kwargs={"store_pk": self.store.pk, "purchase_pk": purchase.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], purchase.pk)

    def test_update_purchase(self):
        purchase = self._create_purchase()
        url = reverse("purchase-detail", kwargs={"store_pk": self.store.pk, "purchase_pk": purchase.pk})
        response = self.client.patch(url, {"reception_checked": True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        purchase.refresh_from_db()
        self.assertTrue(purchase.reception_checked)

    def test_filter_by_supplier(self):
        other_supplier = Supplier.objects.create(store=self.store, name="Beta")
        self._create_purchase(supplier=self.supplier)
        self._create_purchase(supplier=other_supplier)
        response = self.client.get(self.url, {"supplier": self.supplier.pk})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["supplier"], self.supplier.pk)

    def test_filter_by_order_number(self):
        self._create_purchase(order_number="CMD-001")
        self._create_purchase(order_number="CMD-002")
        response = self.client.get(self.url, {"order_number": "001"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["order_number"], "CMD-001")

    def test_ordering_by_order_date_asc(self):
        self._create_purchase(order_date=date(2026, 3, 1), order_number="late")
        self._create_purchase(order_date=date(2026, 1, 1), order_number="early")
        response = self.client.get(self.url, {"ordering": "order_date"})
        order_numbers = [r["order_number"] for r in response.data["results"]]
        self.assertEqual(order_numbers, ["early", "late"])

    def test_ordering_by_order_date_desc(self):
        self._create_purchase(order_date=date(2026, 3, 1), order_number="late")
        self._create_purchase(order_date=date(2026, 1, 1), order_number="early")
        response = self.client.get(self.url, {"ordering": "-order_date"})
        order_numbers = [r["order_number"] for r in response.data["results"]]
        self.assertEqual(order_numbers, ["late", "early"])

    def test_ordering_by_supplier(self):
        supplier_b = Supplier.objects.create(store=self.store, name="Beta")
        self._create_purchase(supplier=supplier_b, order_number="beta")
        self._create_purchase(supplier=self.supplier, order_number="acme")
        response = self.client.get(self.url, {"ordering": "supplier"})
        order_numbers = [r["order_number"] for r in response.data["results"]]
        self.assertEqual(order_numbers, ["acme", "beta"])

    def test_ordering_by_price(self):
        self._create_purchase(price="100.00", order_number="expensive")
        self._create_purchase(price="10.00", order_number="cheap")
        response = self.client.get(self.url, {"ordering": "price"})
        order_numbers = [r["order_number"] for r in response.data["results"]]
        self.assertEqual(order_numbers, ["cheap", "expensive"])

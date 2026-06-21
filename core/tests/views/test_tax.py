import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Store, Tax


class BaseTaxViewSetTestCase(TestCase):
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

    def _create_tax(self, quarter="2024/01", amount="134.00", payment_date=None):
        return Tax.objects.create(
            store=self.store,
            quarter=quarter,
            amount=Decimal(amount),
            payment_date=payment_date,
        )

    @property
    def list_url(self):
        return reverse("tax-list", kwargs={"store_pk": self.store.pk})

    def detail_url(self, tax):
        return reverse("tax-detail", kwargs={"store_pk": self.store.pk, "tax_pk": tax.pk})


class TaxListTest(BaseTaxViewSetTestCase):
    def test_returns_200(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_403(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("tax-list", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_taxes_for_store(self):
        self._create_tax(quarter="2024/01")
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["quarter"], "2024/01")

    def test_does_not_return_other_store_taxes(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        Tax.objects.create(store=other_store, quarter="2024/01", amount=Decimal("50.00"))
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_ordered_by_quarter_descending(self):
        self._create_tax(quarter="2024/01")
        self._create_tax(quarter="2024/02")
        response = self.client.get(self.list_url)
        quarters = [r["quarter"] for r in response.data["results"]]
        self.assertEqual(quarters, ["2024/02", "2024/01"])

    def test_filter_by_quarter(self):
        self._create_tax(quarter="2024/01")
        self._create_tax(quarter="2024/02")
        response = self.client.get(self.list_url, {"quarter": "2024/01"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["quarter"], "2024/01")

    def test_filter_has_payment_true(self):
        self._create_tax(quarter="2024/01", payment_date=datetime.date(2024, 4, 30))
        self._create_tax(quarter="2024/02")
        response = self.client.get(self.list_url, {"has_payment": "true"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["quarter"], "2024/01")


class TaxRetrieveTest(BaseTaxViewSetTestCase):
    def test_returns_200(self):
        tax = self._create_tax()
        response = self.client.get(self.detail_url(tax))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_quarter_is_present(self):
        tax = self._create_tax(quarter="2024/01")
        response = self.client.get(self.detail_url(tax))
        self.assertEqual(response.data["quarter"], "2024/01")


class TaxUpdateTest(BaseTaxViewSetTestCase):
    def test_can_set_payment_date(self):
        tax = self._create_tax()
        response = self.client.patch(self.detail_url(tax), {"payment_date": "2024-04-30"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tax.refresh_from_db()
        self.assertEqual(tax.payment_date, datetime.date(2024, 4, 30))

    def test_quarter_is_read_only(self):
        tax = self._create_tax(quarter="2024/01")
        self.client.patch(self.detail_url(tax), {"quarter": "2099/04"}, format="json")
        tax.refresh_from_db()
        self.assertEqual(tax.quarter, "2024/01")

    def test_amount_is_writable(self):
        tax = self._create_tax(amount="100.00")
        response = self.client.patch(self.detail_url(tax), {"amount": "999.00"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tax.refresh_from_db()
        self.assertEqual(tax.amount, Decimal("999.00"))

    def test_locked_once_payment_date_set(self):
        tax = self._create_tax(payment_date=datetime.date(2024, 4, 30))
        response = self.client.patch(self.detail_url(tax), {"payment_date": "2024-05-01"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_create_via_post(self):
        response = self.client.post(self.list_url, {"quarter": "2024/03", "amount": "50.00"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_delete(self):
        tax = self._create_tax()
        response = self.client.delete(self.detail_url(tax))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

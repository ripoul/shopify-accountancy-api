import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Royalty, Store


class BaseRoyaltyViewSetTestCase(TestCase):
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

    def _create_royalty(self, quarter="2024/01", amount="50.00", payment_date=None):
        return Royalty.objects.create(
            store=self.store,
            quarter=quarter,
            amount=Decimal(amount),
            payment_date=payment_date,
        )

    @property
    def list_url(self):
        return reverse("royalty-list", kwargs={"store_pk": self.store.pk})

    def detail_url(self, royalty):
        return reverse("royalty-detail", kwargs={"store_pk": self.store.pk, "royalty_pk": royalty.pk})


class RoyaltyListTest(BaseRoyaltyViewSetTestCase):
    def test_returns_200(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("royalty-list", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_royalties_for_store(self):
        self._create_royalty(quarter="2024/01")
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["quarter"], "2024/01")

    def test_does_not_return_other_store_royalties(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        Royalty.objects.create(store=other_store, quarter="2024/01", amount=Decimal("50.00"))
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_ordered_by_quarter_descending(self):
        self._create_royalty(quarter="2024/01")
        self._create_royalty(quarter="2024/02")
        response = self.client.get(self.list_url)
        quarters = [r["quarter"] for r in response.data["results"]]
        self.assertEqual(quarters, ["2024/02", "2024/01"])

    def test_filter_by_quarter(self):
        self._create_royalty(quarter="2024/01")
        self._create_royalty(quarter="2024/02")
        response = self.client.get(self.list_url, {"quarter": "2024/01"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["quarter"], "2024/01")

    def test_filter_has_payment_true(self):
        self._create_royalty(quarter="2024/01", payment_date=datetime.date(2024, 4, 30))
        self._create_royalty(quarter="2024/02")
        response = self.client.get(self.list_url, {"has_payment": "true"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["quarter"], "2024/01")


class RoyaltyRetrieveTest(BaseRoyaltyViewSetTestCase):
    def test_returns_200(self):
        royalty = self._create_royalty()
        response = self.client.get(self.detail_url(royalty))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_quarter_is_present(self):
        royalty = self._create_royalty(quarter="2024/01")
        response = self.client.get(self.detail_url(royalty))
        self.assertEqual(response.data["quarter"], "2024/01")

    def test_breakdown_columns_present_in_response(self):
        royalty = self._create_royalty()
        response = self.client.get(self.detail_url(royalty))
        self.assertIn("sum_after_tax_result", response.data)
        self.assertIn("sum_purchase_price", response.data)

    def test_breakdown_columns_read_only(self):
        royalty = self._create_royalty()
        self.client.patch(
            self.detail_url(royalty),
            {"sum_after_tax_result": "9999.00", "sum_purchase_price": "9999.00"},
            format="json",
        )
        royalty.refresh_from_db()
        self.assertNotEqual(royalty.sum_after_tax_result, Decimal("9999.00"))
        self.assertNotEqual(royalty.sum_purchase_price, Decimal("9999.00"))


class RoyaltyUpdateTest(BaseRoyaltyViewSetTestCase):
    def test_can_set_payment_date(self):
        royalty = self._create_royalty()
        response = self.client.patch(self.detail_url(royalty), {"payment_date": "2024-04-30"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        royalty.refresh_from_db()
        self.assertEqual(royalty.payment_date, datetime.date(2024, 4, 30))

    def test_quarter_is_read_only(self):
        royalty = self._create_royalty(quarter="2024/01")
        self.client.patch(self.detail_url(royalty), {"quarter": "2099/04"}, format="json")
        royalty.refresh_from_db()
        self.assertEqual(royalty.quarter, "2024/01")

    def test_amount_is_writable(self):
        royalty = self._create_royalty(amount="50.00")
        response = self.client.patch(self.detail_url(royalty), {"amount": "999.00"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        royalty.refresh_from_db()
        self.assertEqual(royalty.amount, Decimal("999.00"))

    def test_locked_once_payment_date_set(self):
        royalty = self._create_royalty(payment_date=datetime.date(2024, 4, 30))
        response = self.client.patch(self.detail_url(royalty), {"payment_date": "2024-05-01"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_create_via_post(self):
        response = self.client.post(self.list_url, {"quarter": "2024/03", "amount": "50.00"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_delete(self):
        royalty = self._create_royalty()
        response = self.client.delete(self.detail_url(royalty))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class StoreRoyaltyRateUpdateTest(BaseRoyaltyViewSetTestCase):
    @property
    def store_detail_url(self):
        return reverse("store-detail", kwargs={"pk": self.store.pk})

    def test_can_update_royalty_rate(self):
        response = self.client.patch(self.store_detail_url, {"royalty_rate": "15.00"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.store.refresh_from_db()
        self.assertEqual(self.store.royalty_rate, Decimal("15.00"))

    def test_royalty_rate_in_store_response(self):
        response = self.client.get(self.list_url)
        store_response = self.client.get(self.store_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("royalty_rate", store_response.data)

    def test_royalty_rate_defaults_to_zero(self):
        response = self.client.get(self.store_detail_url)
        self.assertEqual(response.data["royalty_rate"], "0.00")

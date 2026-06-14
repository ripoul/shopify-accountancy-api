import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from core.models import CashTransaction, Store


class BaseCashTransactionViewSetTestCase(TestCase):
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

    def _create_transaction(self, amount="20.00", date=None, title="Espèces"):
        return CashTransaction.objects.create(
            store=self.store,
            title=title,
            date=date or datetime.date(2024, 3, 15),
            amount=Decimal(amount),
            source=CashTransaction.Source.ORDER,
        )

    @property
    def list_url(self):
        return reverse("cash-transaction-list", kwargs={"store_pk": self.store.pk})

    def detail_url(self, txn):
        return reverse(
            "cash-transaction-detail",
            kwargs={"store_pk": self.store.pk, "cash_transaction_pk": txn.pk},
        )


class CashTransactionListTest(BaseCashTransactionViewSetTestCase):
    def test_returns_200(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("cash-transaction-list", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_transactions_for_store(self):
        self._create_transaction(amount="30.00")
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["amount"], "30.00")

    def test_does_not_return_other_store_transactions(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        CashTransaction.objects.create(
            store=other_store,
            title="Other",
            date=datetime.date(2024, 1, 1),
            amount=Decimal("99.00"),
            source=CashTransaction.Source.ORDER,
        )
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_ordered_by_date_desc_by_default(self):
        self._create_transaction(date=datetime.date(2024, 1, 1), title="Old")
        self._create_transaction(date=datetime.date(2024, 6, 1), title="New")
        response = self.client.get(self.list_url)
        titles = [r["title"] for r in response.data["results"]]
        self.assertEqual(titles, ["New", "Old"])

    def test_filter_by_date_after(self):
        self._create_transaction(date=datetime.date(2024, 1, 1), title="Old")
        self._create_transaction(date=datetime.date(2024, 6, 1), title="New")
        response = self.client.get(self.list_url, {"date_after": "2024-03-01"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "New")

    def test_filter_by_date_before(self):
        self._create_transaction(date=datetime.date(2024, 1, 1), title="Old")
        self._create_transaction(date=datetime.date(2024, 6, 1), title="New")
        response = self.client.get(self.list_url, {"date_before": "2024-03-01"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "Old")

    def test_ordering_by_amount_asc(self):
        self._create_transaction(amount="50.00", date=datetime.date(2024, 3, 1))
        self._create_transaction(amount="10.00", date=datetime.date(2024, 3, 2))
        response = self.client.get(self.list_url, {"ordering": "amount"})
        amounts = [r["amount"] for r in response.data["results"]]
        self.assertEqual(amounts[0], "10.00")

    def test_ordering_by_date_asc(self):
        self._create_transaction(date=datetime.date(2024, 1, 1), title="Old")
        self._create_transaction(date=datetime.date(2024, 6, 1), title="New")
        response = self.client.get(self.list_url, {"ordering": "date"})
        titles = [r["title"] for r in response.data["results"]]
        self.assertEqual(titles, ["Old", "New"])

    def test_response_contains_expected_fields(self):
        self._create_transaction()
        response = self.client.get(self.list_url)
        result = response.data["results"][0]
        for field in ["id", "title", "date", "amount", "source", "order", "created_at", "updated_at"]:
            self.assertIn(field, result)


class CashTransactionCreateTest(BaseCashTransactionViewSetTestCase):
    def test_create_returns_201(self):
        response = self.client.post(
            self.list_url, {"title": "Espèces", "date": "2024-03-15", "amount": "20.00", "source": "ADD_MONEY"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_without_source_returns_400(self):
        response = self.client.post(self.list_url, {"title": "Espèces", "date": "2024-03-15", "amount": "20.00"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_respects_source_field(self):
        self.client.post(
            self.list_url, {"title": "Retrait", "date": "2024-03-15", "amount": "-13.00", "source": "WITHDRAW_MONEY"}
        )
        txn = CashTransaction.objects.get(store=self.store)
        self.assertEqual(txn.source, CashTransaction.Source.WITHDRAW_MONEY)

    def test_create_with_add_money_source(self):
        self.client.post(
            self.list_url, {"title": "Dépôt", "date": "2024-03-15", "amount": "50.00", "source": "ADD_MONEY"}
        )
        txn = CashTransaction.objects.get(store=self.store)
        self.assertEqual(txn.source, CashTransaction.Source.ADD_MONEY)

    def test_create_links_to_store(self):
        self.client.post(
            self.list_url, {"title": "Espèces", "date": "2024-03-15", "amount": "20.00", "source": "ADD_MONEY"}
        )
        txn = CashTransaction.objects.get(store=self.store)
        self.assertEqual(txn.store, self.store)

    def test_create_increments_store_cash_amount(self):
        self.client.post(
            self.list_url, {"title": "Espèces", "date": "2024-03-15", "amount": "20.00", "source": "ADD_MONEY"}
        )
        self.store.refresh_from_db()
        self.assertEqual(self.store.cash_amount, Decimal("20.00"))

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.post(
            self.list_url, {"title": "Espèces", "date": "2024-03-15", "amount": "20.00", "source": "ADD_MONEY"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CashTransactionUpdateTest(BaseCashTransactionViewSetTestCase):
    def test_patch_returns_200(self):
        txn = self._create_transaction()
        response = self.client.patch(self.detail_url(txn), {"amount": "35.00"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_patch_title(self):
        txn = self._create_transaction(title="Old title")
        self.client.patch(self.detail_url(txn), {"title": "New title"})
        txn.refresh_from_db()
        self.assertEqual(txn.title, "New title")

    def test_patch_date(self):
        txn = self._create_transaction(date=datetime.date(2024, 1, 1))
        self.client.patch(self.detail_url(txn), {"date": "2024-06-15"})
        txn.refresh_from_db()
        self.assertEqual(txn.date, datetime.date(2024, 6, 15))

    def test_patch_amount(self):
        txn = self._create_transaction(amount="20.00")
        self.client.patch(self.detail_url(txn), {"amount": "35.00"})
        txn.refresh_from_db()
        self.assertEqual(txn.amount, Decimal("35.00"))

    def test_source_can_be_updated(self):
        txn = self._create_transaction()
        self.client.patch(self.detail_url(txn), {"source": "OTHER"})
        txn.refresh_from_db()
        self.assertEqual(txn.source, CashTransaction.Source.OTHER)

    def test_unauthenticated_returns_401(self):
        txn = self._create_transaction()
        self.client.credentials()
        response = self.client.patch(self.detail_url(txn), {"amount": "35.00"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CashTransactionDeleteTest(BaseCashTransactionViewSetTestCase):
    def test_delete_returns_204(self):
        txn = self._create_transaction()
        response = self.client.delete(self.detail_url(txn))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_removes_transaction(self):
        txn = self._create_transaction()
        self.client.delete(self.detail_url(txn))
        self.assertFalse(CashTransaction.objects.filter(pk=txn.pk).exists())

    def test_unauthenticated_returns_401(self):
        txn = self._create_transaction()
        self.client.credentials()
        response = self.client.delete(self.detail_url(txn))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_store_transaction_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        txn = CashTransaction.objects.create(
            store=other_store,
            title="Other",
            date=datetime.date(2024, 1, 1),
            amount=Decimal("10.00"),
            source=CashTransaction.Source.ORDER,
        )
        url = reverse(
            "cash-transaction-detail",
            kwargs={"store_pk": other_store.pk, "cash_transaction_pk": txn.pk},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Store, Supplier


class BaseSupplierViewSetTestCase(TestCase):
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

    def _create_supplier(self, name="Acme", store=None):
        return Supplier.objects.create(store=store or self.store, name=name)


class SupplierViewSetTest(BaseSupplierViewSetTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("supplier-list", kwargs={"store_pk": self.store.pk})

    def test_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("supplier-list", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_suppliers_for_store(self):
        self._create_supplier()
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Acme")

    def test_does_not_return_other_store_suppliers(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        Supplier.objects.create(store=other_store, name="Other Supplier")
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_create_assigns_store(self):
        response = self.client.post(self.url, {"name": "New Supplier"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        supplier = Supplier.objects.get(pk=response.data["id"])
        self.assertEqual(supplier.store, self.store)
        self.assertEqual(supplier.name, "New Supplier")

    def test_retrieve_returns_supplier(self):
        supplier = self._create_supplier()
        url = reverse("supplier-detail", kwargs={"store_pk": self.store.pk, "supplier_pk": supplier.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Acme")

    def test_update_supplier(self):
        supplier = self._create_supplier()
        url = reverse("supplier-detail", kwargs={"store_pk": self.store.pk, "supplier_pk": supplier.pk})
        response = self.client.patch(url, {"name": "Renamed"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        supplier.refresh_from_db()
        self.assertEqual(supplier.name, "Renamed")

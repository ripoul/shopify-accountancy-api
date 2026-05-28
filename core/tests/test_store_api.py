from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import get_objects_for_user
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Store

SHOPIFY_PAYLOAD = {
    "shop": "test-store.myshopify.com",
    "code": "abc123",
    "hmac": "validhmac",
    "state": "nonce",
    "timestamp": "1234567890",
}

SHOPIFY_EXCHANGE_RESULT = {
    "access_token": "shpat_test_token",
    "scopes": "read_orders,read_products",
    "name": "Test Store",
}


class StoreConnectTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="strongpassword",
        )
        self.url = reverse("store-list")
        self._authenticate()

    def _authenticate(self):
        token_response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "owner@example.com", "password": "strongpassword"},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

    @patch("core.views.store.exchange_shopify_code", return_value=SHOPIFY_EXCHANGE_RESULT)
    def test_connect_store_success(self, _mock):
        response = self.client.post(self.url, SHOPIFY_PAYLOAD)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["shop_domain"], "test-store.myshopify.com")
        self.assertEqual(response.data["name"], "Test Store")
        self.assertNotIn("access_token", response.data)

    @patch("core.views.store.exchange_shopify_code", return_value=SHOPIFY_EXCHANGE_RESULT)
    def test_connect_store_assigns_can_manage(self, _mock):
        self.client.post(self.url, SHOPIFY_PAYLOAD)
        store = Store.objects.get(shop_domain="test-store.myshopify.com")
        managed = get_objects_for_user(self.user, "core.can_manage", Store)
        self.assertIn(store, managed)

    @patch("core.views.store.exchange_shopify_code", side_effect=ValueError("HMAC invalide."))
    def test_connect_store_invalid_hmac(self, _mock):
        response = self.client.post(self.url, SHOPIFY_PAYLOAD)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("HMAC invalide", response.data["detail"])

    @patch("core.views.store.exchange_shopify_code", return_value=SHOPIFY_EXCHANGE_RESULT)
    def test_connect_store_reinstall_updates_token(self, _mock):
        self.client.post(self.url, SHOPIFY_PAYLOAD)
        updated_result = {**SHOPIFY_EXCHANGE_RESULT, "access_token": "shpat_new_token"}
        with patch("core.views.store.exchange_shopify_code", return_value=updated_result):
            response = self.client.post(self.url, SHOPIFY_PAYLOAD)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Store.objects.filter(shop_domain="test-store.myshopify.com").count(), 1)

    def test_connect_store_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(self.url, SHOPIFY_PAYLOAD)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class StoreListTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(
            username="user1@example.com", email="user1@example.com", password="strongpassword"
        )
        self.user2 = User.objects.create_user(
            username="user2@example.com", email="user2@example.com", password="strongpassword"
        )
        self.url = reverse("store-list")

    def _authenticate(self, user):
        token_response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": user.username, "password": "strongpassword"},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

    @patch("core.views.store.exchange_shopify_code", return_value=SHOPIFY_EXCHANGE_RESULT)
    def test_list_only_returns_own_stores(self, _mock):
        self._authenticate(self.user1)
        self.client.post(self.url, SHOPIFY_PAYLOAD)

        self._authenticate(self.user2)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    @patch("core.views.store.exchange_shopify_code", return_value=SHOPIFY_EXCHANGE_RESULT)
    def test_list_returns_own_stores(self, _mock):
        self._authenticate(self.user1)
        self.client.post(self.url, SHOPIFY_PAYLOAD)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm, get_objects_for_user
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

SHOPIFY_INSTALL_PARAMS = {
    "shop": "test-store.myshopify.com",
    "hmac": "validhmac",
    "host": "aGVsbG8=",
    "timestamp": "1234567890",
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

    def test_list_unauthenticated(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class StoreInstallTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="strongpassword",
        )
        self.url = reverse("store-install")
        self._authenticate()

    def _authenticate(self):
        token_response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "owner@example.com", "password": "strongpassword"},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

    @patch(
        "core.views.store.build_authorization_url",
        return_value="https://test-store.myshopify.com/admin/oauth/authorize",
    )
    def test_install_returns_authorization_url(self, _mock):
        response = self.client.get(self.url, SHOPIFY_INSTALL_PARAMS)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("authorization_url", response.data)
        self.assertEqual(
            response.data["authorization_url"],
            "https://test-store.myshopify.com/admin/oauth/authorize",
        )

    @patch(
        "core.views.store.build_authorization_url",
        side_effect=ValueError("HMAC invalide."),
    )
    def test_install_invalid_hmac_returns_400(self, _mock):
        response = self.client.get(self.url, SHOPIFY_INSTALL_PARAMS)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("HMAC invalide", response.data["detail"])

    def test_install_missing_shop_returns_400(self):
        params = {k: v for k, v in SHOPIFY_INSTALL_PARAMS.items() if k != "shop"}
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_install_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(self.url, SHOPIFY_INSTALL_PARAMS)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class StoreImportProductsTest(TestCase):
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
        self.url = reverse("store-import-products", kwargs={"pk": self.store.pk})

    def _authenticate(self, user):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": user.username, "password": "strongpassword"},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    @patch("core.views.store.import_products")
    def test_success_returns_204(self, _mock):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @patch("core.views.store.import_products")
    def test_calls_import_products_with_store(self, mock_import):
        self.client.post(self.url)
        mock_import.assert_called_once_with(self.store)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("store-import-products", kwargs={"pk": other_store.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

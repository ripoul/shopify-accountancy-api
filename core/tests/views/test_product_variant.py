from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Product, ProductVariant, Store


class ProductVariantViewSetTest(TestCase):
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
        self.product = Product.objects.create(
            store=self.store,
            external_id="gid://shopify/Product/1",
            title="T-shirt",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            external_id="gid://shopify/ProductVariant/1",
            title="M",
            price="29.99",
        )
        self.url = reverse(
            "product-variant-detail",
            kwargs={"store_pk": self.store.pk, "variant_pk": self.variant.pk},
        )

    def _authenticate(self, user):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": user.username, "password": "strongpassword"},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_updates_distributor_price(self):
        response = self.client.patch(self.url, {"distributor_price": "12.34"})

        self.variant.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(self.variant.distributor_price), "12.34")
        self.assertEqual(response.data["distributor_price"], "12.34")

    def test_only_updates_distributor_price(self):
        response = self.client.patch(self.url, {"title": "Changed", "distributor_price": "12.34"})

        self.variant.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.variant.title, "M")
        self.assertEqual(str(self.variant.distributor_price), "12.34")

    def test_invalid_distributor_price_returns_400(self):
        response = self.client.patch(self.url, {"distributor_price": "invalid"})

        self.variant.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsNone(self.variant.distributor_price)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()

        response = self.client.patch(self.url, {"distributor_price": "12.34"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_variant_from_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        other_product = Product.objects.create(
            store=other_store,
            external_id="gid://shopify/Product/99",
            title="Other",
        )
        other_variant = ProductVariant.objects.create(
            product=other_product,
            external_id="gid://shopify/ProductVariant/99",
            title="Other",
            price="99.99",
        )
        url = reverse(
            "product-variant-detail",
            kwargs={"store_pk": other_store.pk, "variant_pk": other_variant.pk},
        )

        response = self.client.patch(url, {"distributor_price": "12.34"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

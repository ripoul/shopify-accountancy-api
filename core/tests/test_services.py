from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.services import build_authorization_url, exchange_shopify_code


class BuildAuthorizationUrlTest(TestCase):
    def setUp(self):
        self.shop = "test-store.myshopify.com"
        self.params = {
            "shop": self.shop,
            "hmac": "validhmac",
            "host": "aGVsbG8=",
            "timestamp": "1234567890",
        }

    @patch("core.services.shopify")
    @patch("core.services.secrets.token_hex", return_value="teststate123")
    @patch("core.services.cache.set")
    def test_returns_authorization_url(self, mock_cache_set, mock_token_hex, mock_shopify):
        mock_shopify.Session.validate_params.return_value = True
        mock_session = MagicMock()
        mock_session.create_permission_url.return_value = "https://test-store.myshopify.com/admin/oauth/authorize"
        mock_shopify.Session.return_value = mock_session

        result = build_authorization_url(self.shop, self.params)

        self.assertEqual(result, "https://test-store.myshopify.com/admin/oauth/authorize")

    @patch("core.services.shopify")
    @patch("core.services.secrets.token_hex", return_value="teststate123")
    @patch("core.services.cache.set")
    def test_caches_state_with_ttl(self, mock_cache_set, mock_token_hex, mock_shopify):
        mock_shopify.Session.validate_params.return_value = True
        mock_shopify.Session.return_value = MagicMock()

        build_authorization_url(self.shop, self.params)

        mock_cache_set.assert_called_once_with(f"shopify_state:{self.shop}", "teststate123", timeout=600)

    @patch("core.services.shopify")
    def test_raises_value_error_on_invalid_hmac(self, mock_shopify):
        mock_shopify.Session.validate_params.return_value = False

        with self.assertRaises(ValueError) as ctx:
            build_authorization_url(self.shop, self.params)

        self.assertIn("HMAC", str(ctx.exception))

    @patch("core.services.shopify")
    @patch("core.services.secrets.token_hex", return_value="teststate123")
    @patch("core.services.cache.set")
    def test_calls_setup_shopify(self, mock_cache_set, mock_token_hex, mock_shopify):
        mock_shopify.Session.validate_params.return_value = True
        mock_shopify.Session.return_value = MagicMock()

        build_authorization_url(self.shop, self.params)

        mock_shopify.Session.setup.assert_called_once()


class ExchangeShopifyCodeTest(TestCase):
    def setUp(self):
        self.shop = "test-store.myshopify.com"
        self.params = {
            "shop": self.shop,
            "code": "abc123",
            "hmac": "validhmac",
            "state": "nonce",
            "timestamp": "1234567890",
        }

    def _make_mock_shopify(self, mock_shopify, token="shpat_test", scopes="read_orders", shop_name="My Store"):
        mock_session = MagicMock()
        mock_session.request_token.return_value = token
        mock_session.access_scopes = scopes
        mock_shopify.Session.return_value = mock_session
        mock_shopify.Session.validate_params.return_value = True
        mock_shop = MagicMock()
        mock_shop.name = shop_name
        mock_shopify.Shop.current.return_value = mock_shop
        return mock_session

    @patch("core.services.shopify")
    def test_returns_token_scopes_and_name(self, mock_shopify):
        self._make_mock_shopify(
            mock_shopify, token="shpat_test_token", scopes="read_orders,read_products", shop_name="Test Store"
        )

        result = exchange_shopify_code(self.shop, self.params)

        self.assertEqual(result["access_token"], "shpat_test_token")
        self.assertEqual(result["scopes"], "read_orders,read_products")
        self.assertEqual(result["name"], "Test Store")

    @patch("core.services.shopify")
    def test_raises_value_error_on_invalid_hmac(self, mock_shopify):
        mock_shopify.Session.validate_params.return_value = False
        mock_shopify.Session.return_value = MagicMock()

        with self.assertRaises(ValueError) as ctx:
            exchange_shopify_code(self.shop, self.params)

        self.assertIn("HMAC", str(ctx.exception))

    @patch("core.services.shopify")
    def test_activates_and_clears_shopify_session(self, mock_shopify):
        mock_session = self._make_mock_shopify(mock_shopify)

        exchange_shopify_code(self.shop, self.params)

        mock_shopify.ShopifyResource.activate_session.assert_called_once_with(mock_session)
        mock_shopify.ShopifyResource.clear_session.assert_called_once()

    @patch("core.services.shopify")
    def test_calls_setup_shopify(self, mock_shopify):
        self._make_mock_shopify(mock_shopify)

        exchange_shopify_code(self.shop, self.params)

        mock_shopify.Session.setup.assert_called_once()

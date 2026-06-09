from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.shopify import build_authorization_url


class BuildAuthorizationUrlTest(TestCase):
    def setUp(self):
        self.shop = "test-store.myshopify.com"
        self.params = {
            "shop": self.shop,
            "hmac": "validhmac",
            "host": "aGVsbG8=",
            "timestamp": "1234567890",
        }

    @patch("core.shopify.build_authorization_url.setup_session")
    @patch("core.shopify.build_authorization_url.shopify")
    @patch("core.shopify.build_authorization_url.secrets.token_hex", return_value="teststate123")
    @patch("core.shopify.build_authorization_url.cache.set")
    def test_returns_authorization_url(self, mock_cache_set, mock_token_hex, mock_shopify, mock_setup_session):
        mock_shopify.Session.validate_params.return_value = True
        mock_session = MagicMock()
        mock_session.create_permission_url.return_value = "https://test-store.myshopify.com/admin/oauth/authorize"
        mock_shopify.Session.return_value = mock_session

        result = build_authorization_url(self.shop, self.params)

        self.assertEqual(result, "https://test-store.myshopify.com/admin/oauth/authorize")

    @patch("core.shopify.build_authorization_url.setup_session")
    @patch("core.shopify.build_authorization_url.shopify")
    @patch("core.shopify.build_authorization_url.secrets.token_hex", return_value="teststate123")
    @patch("core.shopify.build_authorization_url.cache.set")
    def test_caches_state_with_ttl(self, mock_cache_set, mock_token_hex, mock_shopify, mock_setup_session):
        mock_shopify.Session.validate_params.return_value = True
        mock_shopify.Session.return_value = MagicMock()

        build_authorization_url(self.shop, self.params)

        mock_cache_set.assert_called_once_with(f"shopify_state:{self.shop}", "teststate123", timeout=600)

    @patch("core.shopify.build_authorization_url.setup_session")
    @patch("core.shopify.build_authorization_url.shopify")
    def test_raises_value_error_on_invalid_hmac(self, mock_shopify, mock_setup_session):
        mock_shopify.Session.validate_params.return_value = False

        with self.assertRaises(ValueError) as ctx:
            build_authorization_url(self.shop, self.params)

        self.assertIn("HMAC", str(ctx.exception))

    @patch("core.shopify.build_authorization_url.setup_session")
    @patch("core.shopify.build_authorization_url.shopify")
    @patch("core.shopify.build_authorization_url.secrets.token_hex", return_value="teststate123")
    @patch("core.shopify.build_authorization_url.cache.set")
    def test_calls_setup_shopify(self, mock_cache_set, mock_token_hex, mock_shopify, mock_setup_session):
        mock_shopify.Session.validate_params.return_value = True
        mock_shopify.Session.return_value = MagicMock()

        build_authorization_url(self.shop, self.params)

        mock_setup_session.assert_called_once()

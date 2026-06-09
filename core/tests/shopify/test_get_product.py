import json
from unittest.mock import patch

from django.test import TestCase

from core.models import Store
from core.shopify.get_product import get_product

PRODUCT_NODE = {
    "id": "gid://shopify/Product/1",
    "title": "T-shirt",
    "collections": {"edges": [{"node": {"id": "gid://shopify/Collection/1", "title": "Nouveautés"}}]},
    "variants": {"edges": [{"node": {"id": "gid://shopify/ProductVariant/1", "title": "M", "price": "29.99"}}]},
}


def _gql_response(nodes, has_next=False, cursor=None):
    return json.dumps(
        {
            "data": {
                "products": {
                    "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                    "edges": [{"node": n} for n in nodes],
                }
            }
        }
    )


class GetProductTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )

    @patch("core.shopify.get_product.shopify")
    def test_returns_products(self, mock_shopify):
        mock_shopify.GraphQL.return_value.execute.return_value = _gql_response([PRODUCT_NODE])

        result = get_product(self.store)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "gid://shopify/Product/1")
        self.assertEqual(result[0]["title"], "T-shirt")

    @patch("core.shopify.get_product.shopify")
    def test_paginates_through_all_pages(self, mock_shopify):
        product2 = {**PRODUCT_NODE, "id": "gid://shopify/Product/2", "title": "Pantalon"}
        mock_shopify.GraphQL.return_value.execute.side_effect = [
            _gql_response([PRODUCT_NODE], has_next=True, cursor="cursor1"),
            _gql_response([product2]),
        ]

        result = get_product(self.store)

        self.assertEqual(len(result), 2)
        self.assertEqual(mock_shopify.GraphQL.return_value.execute.call_count, 2)

    @patch("core.shopify.get_product.shopify")
    def test_passes_cursor_on_second_page(self, mock_shopify):
        product2 = {**PRODUCT_NODE, "id": "gid://shopify/Product/2"}
        mock_shopify.GraphQL.return_value.execute.side_effect = [
            _gql_response([PRODUCT_NODE], has_next=True, cursor="abc123"),
            _gql_response([product2]),
        ]

        get_product(self.store)

        second_call_variables = mock_shopify.GraphQL.return_value.execute.call_args_list[1][1]["variables"]
        self.assertEqual(second_call_variables["cursor"], "abc123")

    @patch("core.shopify.get_product.shopify")
    def test_activates_shopify_session(self, mock_shopify):
        mock_shopify.GraphQL.return_value.execute.return_value = _gql_response([])

        get_product(self.store)

        mock_shopify.ShopifyResource.activate_session.assert_called_once()

    @patch("core.shopify.get_product.shopify")
    def test_clears_session_on_success(self, mock_shopify):
        mock_shopify.GraphQL.return_value.execute.return_value = _gql_response([])

        get_product(self.store)

        mock_shopify.ShopifyResource.clear_session.assert_called_once()

    @patch("core.shopify.get_product.shopify")
    def test_clears_session_on_exception(self, mock_shopify):
        mock_shopify.GraphQL.return_value.execute.side_effect = Exception("API error")

        with self.assertRaises(Exception):
            get_product(self.store)

        mock_shopify.ShopifyResource.clear_session.assert_called_once()

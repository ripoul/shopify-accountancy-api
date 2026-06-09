import json

import shopify
from django.conf import settings

QUERY = """
query getProducts($cursor: String) {
  products(first: 250, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        title
        collections(first: 50) {
          edges {
            node {
              id
              title
            }
          }
        }
        variants(first: 100) {
          edges {
            node {
              id
              title
              price
            }
          }
        }
      }
    }
  }
}
"""


def get_product(store):
    session = shopify.Session(store.shop_domain, settings.SHOPIFY_API_VERSION, store.access_token)
    shopify.ShopifyResource.activate_session(session)

    try:
        products = []
        cursor = None

        while True:
            result = shopify.GraphQL().execute(QUERY, variables={"cursor": cursor})
            data = json.loads(result)
            products_data = data["data"]["products"]

            for edge in products_data["edges"]:
                products.append(edge["node"])

            if not products_data["pageInfo"]["hasNextPage"]:
                break

            cursor = products_data["pageInfo"]["endCursor"]

        return products
    finally:
        shopify.ShopifyResource.clear_session()

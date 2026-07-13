import json

import shopify
from django.conf import settings

ORDER_FIELDS = """
fragment OrderFields on Order {
  id
  name
  processedAt
  currencyCode
  paymentGatewayNames
  subtotalPriceSet { shopMoney { amount } }
  totalPriceSet { shopMoney { amount } }
  totalDiscountsSet { shopMoney { amount } }
  lineItems(first: 250) {
    edges {
      node {
        id
        title
        quantity
        variant { id }
        product { id }
        originalUnitPriceSet { shopMoney { amount } }
        discountAllocations {
          allocatedAmountSet { shopMoney { amount } }
          discountApplication { index }
        }
      }
    }
  }
  discountApplications(first: 50) {
    edges {
      node {
        __typename
        index
        ... on DiscountCodeApplication { code }
        ... on AutomaticDiscountApplication { title }
        ... on ManualDiscountApplication { title }
        ... on ScriptDiscountApplication { title }
      }
    }
  }
  transactions(first: 10) {
    kind
    status
    gateway
    formattedGateway
    manualPaymentGateway
    amountSet { shopMoney { amount } }
    fees { amount { amount } }
  }
  returns(first: 10) {
    edges {
      node {
        id
        name
        status
        returnLineItems(first: 10) {
          edges {
            node {
              id
              quantity
              ... on ReturnLineItem {
                withCodeDiscountedTotalPriceSet { shopMoney { amount } }
                fulfillmentLineItem { lineItem { id } }
              }
            }
          }
        }
      }
    }
  }
}
"""

SINGLE_ORDER_QUERY = (
    ORDER_FIELDS
    + """
query getOrder($id: ID!) {
  order(id: $id) {
    ...OrderFields
  }
}
"""
)

ORDERS_QUERY = (
    ORDER_FIELDS
    + """
query getOrders($cursor: String, $query: String) {
  orders(first: 50, after: $cursor, query: $query, sortKey: PROCESSED_AT) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        ...OrderFields
      }
    }
  }
}
"""
)


def get_order(store, since=None, external_id=None):
    """Returns (orders, has_more). Fetches at most one page (50 orders) to avoid timeouts."""
    session = shopify.Session(store.shop_domain, settings.SHOPIFY_API_VERSION, store.access_token)
    shopify.ShopifyResource.activate_session(session)

    try:
        if external_id:
            result = shopify.GraphQL().execute(SINGLE_ORDER_QUERY, variables={"id": external_id})
            data = json.loads(result)
            order = data["data"]["order"]
            return ([order] if order else []), False

        search = f"processed_at:>='{since.isoformat()}'" if since else None

        result = shopify.GraphQL().execute(ORDERS_QUERY, variables={"cursor": None, "query": search})
        data = json.loads(result)
        orders_data = data["data"]["orders"]

        orders = [edge["node"] for edge in orders_data["edges"]]
        has_more = orders_data["pageInfo"]["hasNextPage"]

        return orders, has_more
    finally:
        shopify.ShopifyResource.clear_session()

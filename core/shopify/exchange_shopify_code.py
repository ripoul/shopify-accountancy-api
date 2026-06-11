import shopify
from django.conf import settings

from .setup_session import setup_session


def exchange_shopify_code(shop: str, params: dict) -> dict:
    setup_session()

    session = shopify.Session(shop, settings.SHOPIFY_API_VERSION)

    if not shopify.Session.validate_params(params):
        raise ValueError("HMAC invalide.")

    print(params)
    print(type(params))
    try:
        access_token = session.request_token(params)
    except Exception as e:
        print(f"Error: {e}")
        raise
    print("access token ok")

    shopify.ShopifyResource.activate_session(session)
    print("session activated")
    shop_info = shopify.Shop.current()
    print("shop info ok")
    shopify.ShopifyResource.clear_session()
    print("session cleared")
    return {
        "access_token": access_token,
        "scopes": session.access_scopes,
        "name": shop_info.name,
    }

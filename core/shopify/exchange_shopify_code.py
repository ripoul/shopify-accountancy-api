import shopify
from django.conf import settings

from .setup_session import setup_session


def exchange_shopify_code(shop: str, params: dict) -> dict:
    setup_session()

    session = shopify.Session(shop, settings.SHOPIFY_API_VERSION)

    if not shopify.Session.validate_params(params):
        raise ValueError("HMAC invalide.")

    access_token = session.request_token(params)

    shopify.ShopifyResource.activate_session(session)
    shop_info = shopify.Shop.current()
    shopify.ShopifyResource.clear_session()

    return {
        "access_token": access_token,
        "scopes": session.access_scopes,
        "name": shop_info.name,
    }

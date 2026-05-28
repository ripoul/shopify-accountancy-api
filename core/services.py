import shopify
from django.conf import settings


def _setup_shopify():
    shopify.Session.setup(
        api_key=settings.SHOPIFY_API_KEY,
        secret=settings.SHOPIFY_API_SECRET,
    )


def exchange_shopify_code(shop: str, params: dict) -> dict:
    """
    Validates HMAC and exchanges the OAuth code for an access token.
    Returns dict with access_token, scopes and shop name.
    Raises ValueError if HMAC is invalid.
    """
    _setup_shopify()

    session = shopify.Session(shop, settings.SHOPIFY_API_VERSION)

    if not shopify.Session.validate_params(params):
        raise ValueError("HMAC invalide.")

    access_token = session.request_token(params)

    shopify.ShopifyResource.activate_session(session)
    shop_info = shopify.Shop.current()
    shopify.ShopifyResource.clear_session()

    return {
        "access_token": access_token,
        "scopes": session.token,  # scopes granted
        "name": shop_info.name,
    }

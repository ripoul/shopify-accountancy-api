import secrets

import shopify
from django.conf import settings
from django.core.cache import cache


def _setup_shopify():
    shopify.Session.setup(
        api_key=settings.SHOPIFY_API_KEY,
        secret=settings.SHOPIFY_API_SECRET,
    )


def build_authorization_url(shop: str, params: dict) -> str:
    """
    Validates HMAC of the install request, generates a state nonce stored in cache,
    and returns the Shopify OAuth authorization URL.
    Raises ValueError if HMAC is invalid.
    """
    _setup_shopify()

    if not shopify.Session.validate_params(params):
        raise ValueError("HMAC invalide.")

    state = secrets.token_hex(16)
    cache.set(f"shopify_state:{shop}", state, timeout=600)

    session = shopify.Session(shop, settings.SHOPIFY_API_VERSION)
    return session.create_permission_url(
        settings.SHOPIFY_SCOPES,
        settings.SHOPIFY_REDIRECT_URI,
        state,
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
        "scopes": session.access_scopes,
        "name": shop_info.name,
    }

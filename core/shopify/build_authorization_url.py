import secrets

import shopify
from django.conf import settings
from django.core.cache import cache

from .setup_session import setup_session


def build_authorization_url(shop: str, params: dict) -> str:
    setup_session()

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

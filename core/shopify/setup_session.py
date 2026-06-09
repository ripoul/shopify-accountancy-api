import shopify
from django.conf import settings


def setup_session():
    shopify.Session.setup(
        api_key=settings.SHOPIFY_API_KEY,
        secret=settings.SHOPIFY_API_SECRET,
    )

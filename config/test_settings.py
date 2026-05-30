import os
from importlib import import_module

os.environ.setdefault("SHOPIFY_API_KEY", "test-shopify-api-key")
os.environ.setdefault("SHOPIFY_API_SECRET", "test-shopify-api-secret")
os.environ.setdefault("SHOPIFY_SCOPES", "read_orders,read_products")
os.environ.setdefault("SHOPIFY_REDIRECT_URI", "http://localhost:8000/api/stores/callback/")

settings = import_module("config.settings")

for name in dir(settings):
    if name.isupper():
        globals()[name] = getattr(settings, name)

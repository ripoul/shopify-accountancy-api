from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from core.shopify.force_ipv4 import force_ipv4_for_shopify

        force_ipv4_for_shopify()

        import core.signals  # noqa: F401

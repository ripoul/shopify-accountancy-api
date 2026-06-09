from core.models import Collection, Product, ProductVariant
from core.shopify import get_product


def import_products(store):
    products_data = get_product(store)

    for product_data in products_data:
        product, _ = Product.objects.update_or_create(
            store=store,
            external_id=product_data["id"],
            defaults={"title": product_data["title"]},
        )

        collections = []
        for collection_edge in product_data["collections"]["edges"]:
            collection_data = collection_edge["node"]
            collection, _ = Collection.objects.update_or_create(
                store=store,
                external_id=collection_data["id"],
                defaults={"title": collection_data["title"]},
            )
            collections.append(collection)
        product.collections.set(collections)

        for variant_edge in product_data["variants"]["edges"]:
            variant_data = variant_edge["node"]
            ProductVariant.objects.update_or_create(
                product=product,
                external_id=variant_data["id"],
                defaults={
                    "title": variant_data["title"],
                    "price": variant_data["price"],
                },
            )

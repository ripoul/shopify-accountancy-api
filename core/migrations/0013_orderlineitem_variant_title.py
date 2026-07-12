from django.db import migrations

DEFAULT_VARIANT_TITLE = "Default Title"


def add_variant_to_title(apps, schema_editor):
    OrderLineItem = apps.get_model("core", "OrderLineItem")
    for item in OrderLineItem.objects.select_related("variant").exclude(variant__isnull=True):
        variant_title = item.variant.title
        if not variant_title or variant_title == DEFAULT_VARIANT_TITLE:
            continue
        suffix = f" - {variant_title}"
        if item.title.endswith(suffix):
            continue
        item.title = f"{item.title}{suffix}"
        item.save(update_fields=["title"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_alter_banktransaction_source"),
    ]

    operations = [
        migrations.RunPython(add_variant_to_title, migrations.RunPython.noop),
    ]

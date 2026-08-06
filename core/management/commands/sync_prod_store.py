import os
from urllib.parse import parse_qs, unquote, urlparse

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from core.models import (
    BankTransaction,
    CashTransaction,
    Collection,
    Order,
    OrderDiscount,
    OrderExpense,
    OrderLineItem,
    Product,
    ProductVariant,
    Purchase,
    Return,
    ReturnLineItem,
    Royalty,
    Store,
    Supplier,
    Tax,
)

PROD_ALIAS = "prod_readonly"

# Parent-first: safe order to insert into the local DB. `model=None` is resolved to the
# product/collection M2M through table, which has no `created_at`/`updated_at` of its own.
INSERT_ORDER = [
    ("collections", Collection, "store"),
    ("suppliers", Supplier, "store"),
    ("products", Product, "store"),
    ("variants", ProductVariant, "product__store"),
    ("product_collections", None, "product__store"),
    ("taxes", Tax, "store"),
    ("royalties", Royalty, "store"),
    ("orders", Order, "store"),
    ("order_line_items", OrderLineItem, "order__store"),
    ("order_expenses", OrderExpense, "order__store"),
    ("order_discounts", OrderDiscount, "order__store"),
    ("returns", Return, "order__store"),
    ("return_line_items", ReturnLineItem, "return_ref__order__store"),
    ("purchases", Purchase, "store"),
    ("bank_transactions", BankTransaction, "store"),
    ("cash_transactions", CashTransaction, "store"),
]

STORE_COPY_FIELDS = [
    "name",
    "access_token",
    "scopes",
    "cash_amount",
    "bank_amount",
    "royalty_rate",
    "fixed_costs_reserve",
]
BATCH_SIZE = 500


def parse_database_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise CommandError("--prod-database-url must use postgres:// or postgresql://")
    query = parse_qs(parsed.query)
    host = query["host"][0] if "host" in query else (parsed.hostname or "")
    # Django's ConnectionHandler only back-fills defaults (TIME_ZONE, OPTIONS, TEST, ...) for aliases
    # present in settings.DATABASES the first time it reads them - since we register this alias later
    # at runtime, we must supply a fully-formed config ourselves.
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": host,
        "PORT": str(parsed.port or ""),
        "ATOMIC_REQUESTS": False,
        "AUTOCOMMIT": True,
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": False,
        "OPTIONS": {},
        "TIME_ZONE": None,
        "TEST": {"CHARSET": None, "COLLATION": None, "MIGRATE": True, "MIRROR": None, "NAME": None},
    }


class Command(BaseCommand):
    help = "Replace one store's data in the local DB with a fresh copy from the production DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--shop-domain", required=True, help="shop_domain of the store to sync, e.g. foo.myshopify.com"
        )
        parser.add_argument(
            "--prod-database-url",
            default=os.environ.get("PROD_DATABASE_URL"),
            help="postgres:// URL for the production DB. Defaults to $PROD_DATABASE_URL.",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Only fetch counts from prod, touch nothing locally."
        )
        parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")

    def handle(self, *args, **options):
        shop_domain = options["shop_domain"]
        prod_url = options["prod_database_url"]
        if not prod_url:
            raise CommandError("Pass --prod-database-url or set $PROD_DATABASE_URL.")

        from django.conf import settings

        settings.DATABASES[PROD_ALIAS] = parse_database_url(prod_url)

        try:
            self._run(shop_domain, options["dry_run"], options["yes"])
        finally:
            connections[PROD_ALIAS].close()

    def _run(self, shop_domain, dry_run, skip_confirm):
        try:
            prod_store = Store.objects.using(PROD_ALIAS).get(shop_domain=shop_domain)
        except Store.DoesNotExist as exc:
            raise CommandError(f"No store with shop_domain={shop_domain!r} found in prod.") from exc

        try:
            local_store = Store.objects.using("default").get(shop_domain=shop_domain)
        except Store.DoesNotExist as exc:
            raise CommandError(
                f"No store with shop_domain={shop_domain!r} found locally. This command only replaces "
                "an existing store's data, it does not create a new one."
            ) from exc

        self.stdout.write(f"Fetching data for {shop_domain!r} from prod...")
        fetched = {}
        for key, model, lookup in INSERT_ORDER:
            model = model or Product.collections.through
            rows = list(model.objects.using(PROD_ALIAS).filter(**{lookup: prod_store}).order_by("pk"))
            fetched[key] = rows
            self.stdout.write(f"  {key}: {len(rows)} row(s)")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run - local DB left untouched."))
            return

        if not skip_confirm:
            answer = input(
                f"\nThis will DELETE the local data for store {shop_domain!r} and replace it with the "
                f"counts above. Continue? [y/N] "
            )
            if answer.strip().lower() not in {"y", "yes"}:
                self.stdout.write("Aborted.")
                return

        with transaction.atomic(using="default"):
            self.stdout.write("Deleting local rows...")
            CashTransaction.objects.using("default").filter(store=local_store).delete()
            BankTransaction.objects.using("default").filter(store=local_store).delete()
            Purchase.objects.using("default").filter(store=local_store).delete()
            Order.objects.using("default").filter(store=local_store).delete()
            Royalty.objects.using("default").filter(store=local_store).delete()
            Tax.objects.using("default").filter(store=local_store).delete()
            Product.objects.using("default").filter(store=local_store).delete()
            Supplier.objects.using("default").filter(store=local_store).delete()
            Collection.objects.using("default").filter(store=local_store).delete()

            self.stdout.write("Updating store fields...")
            for field in STORE_COPY_FIELDS:
                setattr(local_store, field, getattr(prod_store, field))
            local_store.save(using="default")

            self.stdout.write("Inserting rows from prod...")
            for key, _model, _lookup in INSERT_ORDER:
                rows = fetched[key]
                if not rows:
                    continue
                model = rows[0].__class__
                # bulk_create stamps auto_now/auto_now_add fields to "now" *on the instances themselves*,
                # so the original prod values must be snapshotted first and restored afterwards.
                has_timestamps = key != "product_collections"
                originals = [(r.created_at, r.updated_at) for r in rows] if has_timestamps else None
                model.objects.using("default").bulk_create(rows, batch_size=BATCH_SIZE)
                if has_timestamps:
                    for row, (created_at, updated_at) in zip(rows, originals):
                        row.created_at = created_at
                        row.updated_at = updated_at
                    model.objects.using("default").bulk_update(
                        rows, ["created_at", "updated_at"], batch_size=BATCH_SIZE
                    )
                self.stdout.write(f"  {key}: {len(rows)} row(s) inserted")

        self.stdout.write(self.style.SUCCESS(f"Done. Store {shop_domain!r} now mirrors prod."))

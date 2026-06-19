from decimal import Decimal

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.business_logic.compute_royalty import recalculate_royalty_for_quarter
from core.models import BankTransaction, Purchase


def _purchase_quarter(purchase):
    date = purchase.order_date
    q = (date.month - 1) // 3 + 1
    return f"{date.year}/{q:02d}"


@receiver(post_save, sender=Purchase)
def create_bank_transaction_for_purchase(sender, instance, created, **kwargs):
    if created:
        BankTransaction.objects.create(
            store=instance.store,
            title=f"Purchase {instance.supplier.name} - {instance.price}",
            date=instance.order_date,
            amount=-Decimal(str(instance.price)),
            source=BankTransaction.Source.PURCHASE,
        )


@receiver(post_save, sender=Purchase)
def update_royalty_on_purchase_save(sender, instance, **kwargs):
    recalculate_royalty_for_quarter(instance.store, _purchase_quarter(instance))


@receiver(post_delete, sender=Purchase)
def update_royalty_on_purchase_delete(sender, instance, **kwargs):
    recalculate_royalty_for_quarter(instance.store, _purchase_quarter(instance))

from decimal import Decimal

from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.models import BankTransaction, CashTransaction, Store


def recount_store_bank_amount(store_id):
    bank_amount = BankTransaction.objects.filter(store_id=store_id).aggregate(total=Sum("amount"))["total"] or Decimal(
        "0"
    )
    Store.objects.filter(pk=store_id).update(bank_amount=bank_amount)


@receiver(post_save, sender=BankTransaction)
def update_store_bank_amount(sender, instance, created, **kwargs):
    recount_store_bank_amount(instance.store_id)
    if created and instance.source == BankTransaction.Source.FILL_CASHBOX:
        CashTransaction.objects.create(
            store=instance.store,
            title="Fill cashbox",
            date=instance.date,
            amount=-instance.amount,
            source=CashTransaction.Source.ADD_MONEY,
        )


@receiver(post_delete, sender=BankTransaction)
def recount_store_bank_amount_on_delete(sender, instance, **kwargs):
    recount_store_bank_amount(instance.store_id)

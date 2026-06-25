from decimal import Decimal

from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.models import BankTransaction, CashTransaction, Store


def recount_store_cash_amount(store_id):
    cash_amount = CashTransaction.objects.filter(store_id=store_id).aggregate(total=Sum("amount"))["total"] or Decimal(
        "0"
    )
    Store.objects.filter(pk=store_id).update(cash_amount=cash_amount)


@receiver(post_save, sender=CashTransaction)
def update_store_cash_amount(sender, instance, created, **kwargs):
    recount_store_cash_amount(instance.store_id)
    if created and instance.source == CashTransaction.Source.WITHDRAW_MONEY:
        BankTransaction.objects.create(
            store=instance.store,
            title=f"Withdrawal of {instance.amount} from cashbox",
            date=instance.date,
            amount=-instance.amount,
            source=BankTransaction.Source.EMPTY_CASHBOX,
        )


@receiver(post_delete, sender=CashTransaction)
def recount_store_cash_amount_on_delete(sender, instance, **kwargs):
    recount_store_cash_amount(instance.store_id)

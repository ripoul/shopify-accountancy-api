from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import BankTransaction, CashTransaction, Store


@receiver(post_save, sender=CashTransaction)
def update_store_cash_amount(sender, instance, created, **kwargs):
    if not created:
        return

    Store.objects.filter(pk=instance.store_id).update(cash_amount=F("cash_amount") + instance.amount)
    if instance.source == CashTransaction.Source.WITHDRAW_MONEY:
        BankTransaction.objects.create(
            store=instance.store,
            title=f"Withdrawal of {instance.amount} from cashbox",
            date=instance.date,
            amount=-instance.amount,
            source=BankTransaction.Source.EMPTY_CASHBOX,
        )

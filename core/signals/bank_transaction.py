from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import BankTransaction, CashTransaction, Store


@receiver(post_save, sender=BankTransaction)
def update_store_bank_amount(sender, instance, created, **kwargs):
    if not created:
        return

    Store.objects.filter(pk=instance.store_id).update(bank_amount=F("bank_amount") + instance.amount)
    if instance.source == BankTransaction.Source.FILL_CASHBOX:
        CashTransaction.objects.create(
            store=instance.store,
            title="Fill cashbox",
            date=instance.date,
            amount=-instance.amount,
            source=CashTransaction.Source.ADD_MONEY,
        )

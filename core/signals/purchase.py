from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import BankTransaction, Purchase


@receiver(post_save, sender=Purchase)
def create_bank_transaction_for_purchase(sender, instance, created, **kwargs):
    if created:
        BankTransaction.objects.create(
            store=instance.store,
            title=f"Purchase {instance.supplier.name} - {instance.price}",
            date=instance.order_date,
            amount=-instance.price,
            source=BankTransaction.Source.PURCHASE,
        )

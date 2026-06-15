from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import BankTransaction, Tax


@receiver(post_save, sender=Tax)
def create_bank_transaction_for_tax_payment(sender, instance, **kwargs):
    if not instance.payment_date:
        return

    BankTransaction.objects.get_or_create(
        tax=instance,
        defaults={
            "store": instance.store,
            "title": f"Tax payment {instance.quarter}",
            "date": instance.payment_date,
            "amount": -instance.amount,
            "source": BankTransaction.Source.TAX,
        },
    )

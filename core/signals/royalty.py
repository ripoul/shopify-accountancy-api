from django.db.models.signals import post_save
from django.dispatch import receiver

from core.business_logic.compute_royalty import recalculate_royalty_for_quarter
from core.models import BankTransaction, Royalty, Tax


@receiver(post_save, sender=Royalty)
def create_bank_transaction_for_royalty_payment(sender, instance, **kwargs):
    if not instance.payment_date:
        return

    BankTransaction.objects.get_or_create(
        royalty=instance,
        defaults={
            "store": instance.store,
            "title": f"Royalty payment {instance.quarter}",
            "date": instance.payment_date,
            "amount": -instance.amount,
            "source": BankTransaction.Source.ROYALTY,
        },
    )


@receiver(post_save, sender=Tax)
def update_royalty_on_tax_change(sender, instance, **kwargs):
    recalculate_royalty_for_quarter(instance.store, instance.quarter)

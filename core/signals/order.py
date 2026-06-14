from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import BankTransaction, CashTransaction, Order, OrderExpense


@receiver(post_save, sender=Order)
def create_cash_transaction_for_order(sender, instance, **kwargs):
    if instance.cash_paid_amount:
        CashTransaction.objects.get_or_create(
            store=instance.store,
            order=instance,
            defaults={
                "title": f"Cash payment for {instance.name}",
                "date": instance.processed_at.date(),
                "amount": instance.cash_paid_amount,
                "source": CashTransaction.Source.ORDER,
            },
        )

    if instance.shopify_transfer_amount:
        BankTransaction.objects.get_or_create(
            store=instance.store,
            order=instance,
            defaults={
                "title": f"Shopify transfer for {instance.name}",
                "date": instance.processed_at.date(),
                "amount": instance.shopify_transfer_amount,
                "source": BankTransaction.Source.ORDER,
            },
        )


@receiver(post_save, sender=OrderExpense)
def create_bank_transaction_for_order_expense(sender, instance, **kwargs):
    if instance.type == OrderExpense.Type.DELIVERY:
        BankTransaction.objects.create(
            store=instance.order.store,
            title=f"Delivery fee for {instance.order.name}",
            date=instance.order.processed_at.date(),
            amount=-instance.amount,
            source=BankTransaction.Source.ORDER,
        )

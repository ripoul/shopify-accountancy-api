from decimal import Decimal

from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.business_logic.compute_royalty import recalculate_royalty_for_quarter
from core.models import BankTransaction, CashTransaction, Order, OrderExpense, Return, Tax

TAX_RATE = Decimal("0.134")


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

    if instance.shopify_transfer_amount and not instance.cash_paid_amount:
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


@receiver(post_save, sender=Order)
def update_quarterly_tax(sender, instance, **kwargs):
    if not instance.quarter:
        return
    try:
        tax = Tax.objects.get(store=instance.store, quarter=instance.quarter)
        if tax.payment_date:
            return
    except Tax.DoesNotExist:
        pass

    total = Order.objects.filter(store=instance.store, quarter=instance.quarter).aggregate(total=Sum("net_revenue"))[
        "total"
    ] or Decimal("0")
    Tax.objects.update_or_create(
        store=instance.store,
        quarter=instance.quarter,
        defaults={"amount": (total * TAX_RATE).quantize(Decimal("0.01"))},
    )


@receiver(post_save, sender=Order)
def update_quarterly_royalty(sender, instance, **kwargs):
    if not instance.quarter:
        return
    recalculate_royalty_for_quarter(instance.store, instance.quarter)


@receiver(post_save, sender=OrderExpense)
def create_bank_transaction_for_order_expense(sender, instance, created, **kwargs):
    if instance.type == OrderExpense.Type.DELIVERY and created:
        BankTransaction.objects.create(
            store=instance.order.store,
            title=f"Delivery fee for {instance.order.name}",
            date=instance.order.processed_at.date(),
            amount=-instance.amount,
            source=BankTransaction.Source.ORDER_DELIVERY,
        )


@receiver(post_save, sender=Return)
def create_bank_transaction_for_return(sender, instance, created, **kwargs):
    if created and instance.amount:
        BankTransaction.objects.create(
            store=instance.order.store,
            title=f"Return {instance.name}",
            date=instance.order.processed_at.date(),
            amount=-instance.amount,
            source=BankTransaction.Source.RETURN,
        )

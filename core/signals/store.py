from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core.business_logic.compute_royalty import compute_royalty_breakdown
from core.models import Royalty, Store


@receiver(pre_save, sender=Store)
def capture_old_royalty_rate(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._royalty_rate_before = Store.objects.get(pk=instance.pk).royalty_rate
        except Store.DoesNotExist:
            instance._royalty_rate_before = instance.royalty_rate
    else:
        instance._royalty_rate_before = instance.royalty_rate


@receiver(post_save, sender=Store)
def recalculate_royalties_on_rate_change(sender, instance, **kwargs):
    old_rate = getattr(instance, "_royalty_rate_before", instance.royalty_rate)
    if old_rate == instance.royalty_rate:
        return

    for royalty in Royalty.objects.filter(store=instance, payment_date__isnull=True):
        order_total, purchase_total, amount = compute_royalty_breakdown(instance, royalty.quarter)
        royalty.amount = amount
        royalty.sum_after_tax_result = order_total
        royalty.sum_purchase_price = purchase_total
        royalty.save(update_fields=["amount", "sum_after_tax_result", "sum_purchase_price", "updated_at"])

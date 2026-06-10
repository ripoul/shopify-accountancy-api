from django.shortcuts import get_object_or_404
from guardian.shortcuts import get_objects_for_user

from core.models import Store


def get_store_for_user(user, store_pk):
    return get_object_or_404(
        get_objects_for_user(user, "core.can_manage", Store),
        pk=store_pk,
    )

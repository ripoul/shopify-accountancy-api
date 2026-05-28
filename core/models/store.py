from django.db import models


class Store(models.Model):
    shop_domain = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    access_token = models.CharField(max_length=255)
    scopes = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            ("can_manage", "Can manage store"),
        ]

    def __str__(self):
        return self.shop_domain

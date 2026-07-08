from django.contrib.auth.models import User
from django.db import models

from core.constants.profile import ProfileLang


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    lang = models.CharField(max_length=5, choices=ProfileLang.get_choices(), default=ProfileLang.EN_US)

    def __str__(self):
        return f"{self.user} ({self.lang})"

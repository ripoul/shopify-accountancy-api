from django.contrib.auth.models import User
from django.test import TestCase

from core.constants.profile import ProfileLang
from core.models import Profile


class CreateProfileForUserSignalTest(TestCase):
    def test_creates_profile_when_user_is_created(self):
        user = User.objects.create_user(
            username="new@example.com",
            email="new@example.com",
            password="strongpassword",
        )

        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_created_profile_defaults_to_english(self):
        user = User.objects.create_user(
            username="new2@example.com",
            email="new2@example.com",
            password="strongpassword",
        )

        self.assertEqual(user.profile.lang, ProfileLang.EN_US)

    def test_does_not_create_duplicate_profile_on_update(self):
        user = User.objects.create_user(
            username="new3@example.com",
            email="new3@example.com",
            password="strongpassword",
        )

        user.first_name = "Updated"
        user.save()

        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from core.constants.profile import ProfileLang
from core.models import Profile


class ProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="jules@example.com",
            email="jules@example.com",
            password="strongpassword",
        )

    def test_profile_is_created_with_default_lang(self):
        self.assertEqual(self.user.profile.lang, ProfileLang.EN_US)

    def test_str_includes_user_and_lang(self):
        self.assertEqual(str(self.user.profile), f"{self.user} (en_US)")

    def test_lang_can_be_set_to_french(self):
        profile = self.user.profile
        profile.lang = ProfileLang.FR_FR
        profile.save()

        profile.refresh_from_db()
        self.assertEqual(profile.lang, "fr_FR")

    def test_lang_can_be_set_to_british_english(self):
        profile = self.user.profile
        profile.lang = ProfileLang.EN_GB
        profile.save()

        profile.refresh_from_db()
        self.assertEqual(profile.lang, "en_GB")

    def test_user_can_only_have_one_profile(self):
        with self.assertRaises(IntegrityError):
            Profile.objects.create(user=self.user)

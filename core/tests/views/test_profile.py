from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class ProfileMeTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="me@example.com",
            email="me@example.com",
            password="strongpassword",
        )
        self.url = reverse("profile-me")

    def _authenticate(self):
        token_response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "me@example.com", "password": "strongpassword"},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

    def test_get_lang(self):
        self._authenticate()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["lang"], "en_US")

    def test_get_unauthenticated(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_lang(self):
        self._authenticate()
        response = self.client.patch(self.url, {"lang": "fr_FR"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["lang"], "fr_FR")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.lang, "fr_FR")

    def test_patch_lang_distinguishes_english_variants(self):
        self._authenticate()
        response = self.client.patch(self.url, {"lang": "en_GB"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["lang"], "en_GB")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.lang, "en_GB")

    def test_put_lang(self):
        self._authenticate()
        response = self.client.put(self.url, {"lang": "fr_FR"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["lang"], "fr_FR")

    def test_patch_unauthenticated(self):
        response = self.client.patch(self.url, {"lang": "fr_FR"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_invalid_lang_rejected(self):
        self._authenticate()
        response = self.client.patch(self.url, {"lang": "xx"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

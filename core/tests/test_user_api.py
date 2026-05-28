from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class UserCreateTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("user-create")
        self.valid_payload = {
            "email": "jules@example.com",
            "first_name": "Jules",
            "last_name": "Le Bris",
            "password": "strongpassword",
        }

    def test_create_user_success(self):
        response = self.client.post(self.url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "jules@example.com")
        self.assertNotIn("password", response.data)

    def test_username_is_set_to_email(self):
        self.client.post(self.url, self.valid_payload)
        user = User.objects.get(email="jules@example.com")
        self.assertEqual(user.username, "jules@example.com")

    def test_create_user_duplicate_email(self):
        self.client.post(self.url, self.valid_payload)
        response = self.client.post(self.url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_user_missing_email(self):
        payload = {**self.valid_payload}
        del payload["email"]
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_user_password_too_short(self):
        response = self.client.post(self.url, {**self.valid_payload, "password": "short"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_user_no_auth_required(self):
        self.client.credentials()
        response = self.client.post(self.url, self.valid_payload)
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserMeTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="me@example.com",
            email="me@example.com",
            first_name="Jules",
            last_name="Le Bris",
            password="strongpassword",
        )
        self.url = reverse("user-me")

    def _authenticate(self):
        token_response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "me@example.com", "password": "strongpassword"},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

    def test_get_me_authenticated(self):
        self._authenticate()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "me@example.com")
        self.assertEqual(response.data["first_name"], "Jules")

    def test_get_me_unauthenticated(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_me(self):
        self._authenticate()
        response = self.client.patch(self.url, {"first_name": "Jean"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Jean")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Jean")

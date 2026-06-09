from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class JWTViewsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="strongpassword",
        )

    def test_obtain_token_returns_access_and_refresh(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "test@example.com", "password": "strongpassword"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_obtain_token_invalid_credentials(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "test@example.com", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token(self):
        obtain_response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "test@example.com", "password": "strongpassword"},
        )
        refresh_token = obtain_response.data["refresh"]

        response = self.client.post(reverse("token_refresh"), {"refresh": refresh_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_refresh_token_invalid(self):
        response = self.client.post(reverse("token_refresh"), {"refresh": "not-a-valid-token"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class OpenAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_schema_endpoint(self):
        response = self.client.get(reverse("schema"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_swagger_ui(self):
        response = self.client.get(reverse("swagger-ui"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_redoc(self):
        response = self.client.get(reverse("redoc"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

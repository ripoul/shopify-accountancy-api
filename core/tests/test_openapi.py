from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


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

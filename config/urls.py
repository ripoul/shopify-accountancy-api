import urllib.request

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


def connectivity_check(request):
    results = {}
    for url in ["https://www.google.com", "https://shopify.com"]:
        try:
            urllib.request.urlopen(url, timeout=5)
            results[url] = "ok"
        except Exception as e:
            results[url] = str(e)
    return JsonResponse(results)


urlpatterns = [
    path("health/connectivity/", connectivity_check),
    path("admin/", admin.site.urls),
    # Auth
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # App
    path("", include("core.urls")),
    # Schema & Docs
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

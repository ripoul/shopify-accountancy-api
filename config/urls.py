import socket
import time
import urllib.request

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


def _tcp_connect(host, family, timeout=5):
    start = time.monotonic()
    sock = None
    try:
        infos = socket.getaddrinfo(host, 443, family, socket.SOCK_STREAM)
        sock = socket.socket(infos[0][0], socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(infos[0][4])
        return {"status": "ok", "address": infos[0][4][0], "elapsed_ms": round((time.monotonic() - start) * 1000)}
    except Exception as e:
        return {"status": "error", "error": str(e), "elapsed_ms": round((time.monotonic() - start) * 1000)}
    finally:
        if sock is not None:
            sock.close()


def _https_get(url, timeout=8):
    start = time.monotonic()
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return {"status": "ok", "elapsed_ms": round((time.monotonic() - start) * 1000)}
    except Exception as e:
        return {"status": "error", "error": str(e), "elapsed_ms": round((time.monotonic() - start) * 1000)}


def connectivity_check(request):
    shop = request.GET.get("shop", "shopify.com")
    return JsonResponse(
        {
            "shop": shop,
            "tcp_ipv4": _tcp_connect(shop, socket.AF_INET),
            "tcp_ipv6": _tcp_connect(shop, socket.AF_INET6),
            "https_google": _https_get("https://www.google.com"),
            "https_shop": _https_get(f"https://{shop}/admin/oauth/access_token"),
        }
    )


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

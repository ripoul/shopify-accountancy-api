from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import StoreViewSet, UserCreateView, UserMeView

router = DefaultRouter()
router.register("stores", StoreViewSet, basename="store")

urlpatterns = [
    path("users/", UserCreateView.as_view(), name="user-create"),
    path("users/me/", UserMeView.as_view(), name="user-me"),
    path("", include(router.urls)),
]

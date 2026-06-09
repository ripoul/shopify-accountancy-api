from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CollectionViewSet, ProductVariantViewSet, ProductViewSet, StoreViewSet, UserCreateView, UserMeView

router = DefaultRouter()
router.register("stores", StoreViewSet, basename="store")
router.register(r"stores/(?P<store_pk>\d+)/products", ProductViewSet, basename="product")
router.register(r"stores/(?P<store_pk>\d+)/products/variants", ProductVariantViewSet, basename="product-variant")
router.register(r"stores/(?P<store_pk>\d+)/products/collections", CollectionViewSet, basename="collection")

urlpatterns = [
    path("users/", UserCreateView.as_view(), name="user-create"),
    path("users/me/", UserMeView.as_view(), name="user-me"),
    path("", include(router.urls)),
]

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BankTransactionViewSet,
    CashTransactionViewSet,
    CollectionViewSet,
    OrderExpenseViewSet,
    OrderLineItemViewSet,
    OrderViewSet,
    ProductVariantViewSet,
    ProductViewSet,
    ProfileMeViewSet,
    PurchaseViewSet,
    RoyaltyViewSet,
    StatsViewSet,
    StoreViewSet,
    SupplierViewSet,
    TaxViewSet,
    UserCreateView,
    UserMeView,
)

router = DefaultRouter()
router.register("stores", StoreViewSet, basename="store")
router.register(r"stores/(?P<store_pk>\d+)/products", ProductViewSet, basename="product")
router.register(r"stores/(?P<store_pk>\d+)/products/variants", ProductVariantViewSet, basename="product-variant")
router.register(r"stores/(?P<store_pk>\d+)/products/collections", CollectionViewSet, basename="collection")
router.register(r"stores/(?P<store_pk>\d+)/suppliers", SupplierViewSet, basename="supplier")
router.register(r"stores/(?P<store_pk>\d+)/purchases", PurchaseViewSet, basename="purchase")
router.register(r"stores/(?P<store_pk>\d+)/orders", OrderViewSet, basename="order")
router.register(
    r"stores/(?P<store_pk>\d+)/orders/(?P<order_pk>\d+)/expenses",
    OrderExpenseViewSet,
    basename="order-expense",
)
router.register(
    r"stores/(?P<store_pk>\d+)/orders/(?P<order_pk>\d+)/line-items",
    OrderLineItemViewSet,
    basename="order-line-item",
)
router.register(r"stores/(?P<store_pk>\d+)/bank-transactions", BankTransactionViewSet, basename="bank-transaction")
router.register(r"stores/(?P<store_pk>\d+)/cash-transactions", CashTransactionViewSet, basename="cash-transaction")
router.register(r"stores/(?P<store_pk>\d+)/taxes", TaxViewSet, basename="tax")
router.register(r"stores/(?P<store_pk>\d+)/royalties", RoyaltyViewSet, basename="royalty")
router.register(r"stores/(?P<store_pk>\d+)/stats", StatsViewSet, basename="stat")

urlpatterns = [
    path("users/", UserCreateView.as_view(), name="user-create"),
    path("users/me/", UserMeView.as_view(), name="user-me"),
    path(
        "users/me/profile/",
        ProfileMeViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"}),
        name="profile-me",
    ),
    path("", include(router.urls)),
]

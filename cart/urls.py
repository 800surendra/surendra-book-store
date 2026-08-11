from django.urls import path

from . import views


app_name = "cart"


urlpatterns = [

    # =====================================================
    # CART
    # =====================================================

    path(
        "",
        views.view_cart,
        name="view",
    ),

    # =====================================================
    # ADD TO CART
    # =====================================================

    path(
        "add/<int:book_id>/",
        views.add_to_cart,
        name="add",
    ),

    # =====================================================
    # UPDATE CART
    # =====================================================

    path(
        "update/<int:item_id>/",
        views.update_cart,
        name="update",
    ),

    # =====================================================
    # REMOVE ITEM
    # =====================================================

    path(
        "remove/<int:item_id>/",
        views.remove_from_cart,
        name="remove",
    ),

    # =====================================================
    # COUPON
    # =====================================================

    path(
        "coupon/apply/",
        views.apply_coupon,
        name="apply_coupon",
    ),

    path(
        "coupon/remove/",
        views.remove_coupon,
        name="remove_coupon",
    ),

    # =====================================================
    # CART COUNT
    # =====================================================

    path(
        "count/",
        views.cart_count,
        name="count",
    ),
]
from django.urls import path
from . import views

app_name = 'orders'
urlpatterns = [
    # My Orders
    path('my-orders/', views.my_orders, name='my_orders'),

    # Order Detail
    path('<int:order_id>/', views.order_detail, name='detail'),

    # Checkout Flow
    path('checkout/delivery/', views.checkout_delivery, name='checkout_delivery'),
    path('checkout/payment-method/', views.payment_method, name='payment_method'),
    path('checkout/payment-screen/', views.payment_screen, name='payment_screen'),
    path('checkout/payment-submit/<int:order_id>/', views.payment_submit, name='payment_submit'),
# Pincode Lookup (NEW)
    path('checkout/pincode-lookup/',                views.pincode_lookup,name='pincode_lookup'),
    # Order Status & Success
    path('status/<int:order_id>/', views.order_status, name='status'),
    path('success/<int:order_id>/', views.order_success, name='success'),

    # Admin Verify
    path('admin/verify/<int:order_id>/', views.admin_verify_payment, name='admin_verify_payment'),
]
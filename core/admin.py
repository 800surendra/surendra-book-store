from django.contrib import admin

from .models import ServiceablePincode


@admin.register(ServiceablePincode)
class ServiceablePincodeAdmin(admin.ModelAdmin):
    list_display = (
        "pincode",
        "area_name",
        "city",
        "state",
        "is_serviceable",
        "cash_on_delivery_available",
        "estimated_delivery_days",
        "shipping_charge",
        "updated_at",
    )
    list_filter = (
        "is_serviceable",
        "cash_on_delivery_available",
        "state",
    )
    search_fields = (
        "pincode",
        "area_name",
        "city",
        "state",
    )
    list_editable = (
        "is_serviceable",
        "cash_on_delivery_available",
        "estimated_delivery_days",
        "shipping_charge",
    )
    ordering = ("state", "city", "pincode")
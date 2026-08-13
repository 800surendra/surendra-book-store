from django.contrib import admin

from .models import Cart, CartItem, Coupon


# =========================================================
# CART ITEM INLINE
# =========================================================

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ("book",)

    fields = (
        "book",
        "quantity",
        "item_total",
    )

    readonly_fields = (
        "item_total",
    )

    def item_total(self, obj):
        if not obj or not obj.pk:
            return "—"

        return f"₹{obj.get_total_price():,.2f}"

    item_total.short_description = "Total"


# =========================================================
# CART ADMIN
# =========================================================

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "cart_owner",
        "total_items",
        "cart_total",
        "created_at",
        "updated_at",
    )

    list_display_links = (
        "id",
        "cart_owner",
    )

    search_fields = (
        "user__username",
        "user__email",
        "session_key",
    )

    list_filter = (
        "created_at",
        "updated_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "cart_total_display",
        "total_items_display",
    )

    fields = (
        "user",
        "session_key",
        "total_items_display",
        "cart_total_display",
        "created_at",
        "updated_at",
    )

    inlines = (
        CartItemInline,
    )

    ordering = (
        "-updated_at",
    )

    list_per_page = 25

    def cart_owner(self, obj):
        if obj.user:
            return obj.user.get_username()

        return "Guest"

    cart_owner.short_description = "Customer"
    cart_owner.admin_order_field = "user__username"

    def total_items(self, obj):
        return obj.get_total_items()

    total_items.short_description = "Items"

    def cart_total(self, obj):
        return f"₹{obj.get_total_price():,.2f}"

    cart_total.short_description = "Cart Total"

    def total_items_display(self, obj):
        return obj.get_total_items()

    total_items_display.short_description = "Total Items"

    def cart_total_display(self, obj):
        return f"₹{obj.get_total_price():,.2f}"

    cart_total_display.short_description = "Current Cart Total"


# =========================================================
# CART ITEM ADMIN
# =========================================================

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "cart",
        "book",
        "quantity",
        "item_total",
    )

    search_fields = (
        "book__title",
        "book__author",
        "cart__user__username",
        "cart__user__email",
    )

    list_filter = (
        "book",
    )

    autocomplete_fields = (
        "cart",
        "book",
    )

    readonly_fields = (
        "item_total",
    )

    fields = (
        "cart",
        "book",
        "quantity",
        "item_total",
    )

    list_per_page = 30

    def item_total(self, obj):
        return f"₹{obj.get_total_price():,.2f}"

    item_total.short_description = "Item Total"


# =========================================================
# COUPON ADMIN
# =========================================================

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "discount_display",
        "minimum_order_value",
        "validity",
        "usage_status",
        "is_active",
    )

    list_display_links = (
        "code",
    )

    search_fields = (
        "code",
    )

    list_filter = (
        "discount_type",
        "is_active",
        "valid_from",
        "valid_until",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 25

    fieldsets = (
        (
            "Coupon Information",
            {
                "fields": (
                    "code",
                    "is_active",
                ),
                "description": "Basic coupon configuration.",
            },
        ),
        (
            "Discount",
            {
                "fields": (
                    "discount_type",
                    "discount_value",
                    "maximum_discount",
                    "minimum_order_value",
                ),
                "description": (
                    "Configure percentage or fixed-value discount."
                ),
            },
        ),
        (
            "Validity",
            {
                "fields": (
                    "valid_from",
                    "valid_until",
                ),
            },
        ),
        (
            "Usage Control",
            {
                "fields": (
                    "usage_limit",
                    "used_count",
                ),
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    readonly_fields = (
        "used_count",
        "created_at",
        "updated_at",
    )

    def discount_display(self, obj):
        if obj.discount_type == Coupon.DISCOUNT_PERCENTAGE:
            return f"{obj.discount_value}%"

        return f"₹{obj.discount_value:,.2f}"

    discount_display.short_description = "Discount"

    def validity(self, obj):
        if obj.valid_from and obj.valid_until:
            return (
                f"{obj.valid_from:%d %b %Y} → "
                f"{obj.valid_until:%d %b %Y}"
            )

        if obj.valid_from:
            return f"From {obj.valid_from:%d %b %Y}"

        if obj.valid_until:
            return f"Until {obj.valid_until:%d %b %Y}"

        return "Unlimited"

    validity.short_description = "Validity"

    def usage_status(self, obj):
        if obj.usage_limit is None:
            return f"{obj.used_count} / ∞"

        return f"{obj.used_count} / {obj.usage_limit}"

    usage_status.short_description = "Usage"
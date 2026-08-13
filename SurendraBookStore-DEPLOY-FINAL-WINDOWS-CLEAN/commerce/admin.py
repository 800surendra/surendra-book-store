from django.contrib import admin
from .models import EBook, EBookAccess, EBookPurchase, WishlistItem, Review, ReturnRequest, Notification, SupportTicket, AuditLog, InventoryMovement

@admin.register(EBook)
class EBookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "price", "discount_percent", "is_available")
    list_filter = ("is_available", "language", "category")
    search_fields = ("title", "author", "description")
    prepopulated_fields = {"slug": ("title",)}

admin.site.register(EBookAccess)
admin.site.register(EBookPurchase)
admin.site.register(WishlistItem)
admin.site.register(Review)
admin.site.register(ReturnRequest)
admin.site.register(Notification)
admin.site.register(SupportTicket)
admin.site.register(AuditLog)
admin.site.register(InventoryMovement)

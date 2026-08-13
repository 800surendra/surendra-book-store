from .models import EBookAccess, EBookPurchase, Notification


def grant_verified_ebook_access(order):
    """Idempotently grants a paid digital item after manual payment verification."""
    purchase = EBookPurchase.objects.filter(order=order).select_related("ebook", "user").first()
    if not purchase:
        return False
    access, created = EBookAccess.objects.get_or_create(user=purchase.user, ebook=purchase.ebook, defaults={"order": order})
    if created:
        Notification.objects.create(user=purchase.user, title="E-book ready", message=f"{purchase.ebook.title} is now available in My E-Books.")
    return created

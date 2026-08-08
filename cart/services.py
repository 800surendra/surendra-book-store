from django.core.exceptions import ValidationError
from django.db import transaction

from books.models import Book

from .models import Cart, CartItem


def get_or_create_cart(request):
    """Return the active cart for the current logged-in user or guest session."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.create()

    cart, _ = Cart.objects.get_or_create(
        session_key=request.session.session_key,
    )
    return cart


@transaction.atomic
def add_book_to_cart(request, book, quantity=1):
    """Add a valid active book to the current cart with stock protection."""
    if book.status != Book.Status.ACTIVE:
        raise ValidationError("This book is not currently available for purchase.")

    if quantity < 1:
        raise ValidationError("Quantity must be at least 1.")

    cart = get_or_create_cart(request)

    cart_item, created = CartItem.objects.select_for_update().get_or_create(
        cart=cart,
        book=book,
        defaults={
            "quantity": quantity,
            "unit_price": book.sale_price,
        },
    )

    if not created:
        cart_item.quantity += quantity
        cart_item.unit_price = book.sale_price

    if cart_item.quantity > book.stock_quantity:
        raise ValidationError(
            f"Only {book.stock_quantity} copy/copies of this book are available."
        )

    cart_item.full_clean()
    cart_item.save()

    return cart, cart_item


@transaction.atomic
def update_cart_item_quantity(cart_item, quantity):
    """Safely update a cart item while respecting live stock availability."""
    if quantity < 1:
        cart_item.delete()
        return None

    if quantity > cart_item.book.stock_quantity:
        raise ValidationError(
            f"Only {cart_item.book.stock_quantity} copy/copies are available."
        )

    cart_item.quantity = quantity
    cart_item.unit_price = cart_item.book.sale_price
    cart_item.full_clean()
    cart_item.save()

    return cart_item
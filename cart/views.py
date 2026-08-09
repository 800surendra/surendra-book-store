from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from books.models import Book

from .models import Cart, CartItem


def get_user_cart(request):
    """
    Logged-in user ke liye sirf usi user ka cart return karega.

    Guest users ke liye cart create nahi hoga.
    """

    if not request.user.is_authenticated:
        return None

    cart, created = Cart.objects.get_or_create(
        user=request.user
    )

    return cart


@login_required(login_url='accounts:login')
def add_to_cart(request, book_id):

    book = get_object_or_404(Book, id=book_id)

    cart = get_user_cart(request)

    if cart is None:
        return redirect('accounts:login')

    # Quantity safely read karo
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1

    # Minimum quantity 1
    quantity = max(quantity, 1)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        book=book
    )

    if created:

        cart_item.quantity = quantity
        cart_item.save()

        message = f'"{book.title}" added to cart!'

    else:

        cart_item.quantity += quantity
        cart_item.save()

        message = f'"{book.title}" quantity updated!'

    messages.success(request, message)

    # AJAX response
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':

        return JsonResponse({
            'status': 'success',
            'cart_count': cart.get_total_items(),
            'cart_total': float(cart.get_total_price()),
            'message': message,
        })

    return redirect(
        request.META.get(
            'HTTP_REFERER',
            'core:home'
        )
    )


@login_required(login_url='accounts:login')
def view_cart(request):

    cart = get_user_cart(request)

    subtotal = Decimal('0')
    delivery_charge = Decimal('0')
    gst = Decimal('0')
    discount = Decimal('0')
    grand_total = Decimal('0')

    if cart:

        subtotal = cart.get_total_price()

        delivery_charge = (
            Decimal('0')
            if subtotal >= Decimal('500')
            else Decimal('50')
        )

        gst = subtotal * Decimal('0.05')

        discount = Decimal('0')

        grand_total = (
            subtotal
            + delivery_charge
            + gst
            - discount
        )

    context = {
        'cart': cart,
        'subtotal': subtotal,
        'delivery_charge': delivery_charge,
        'gst': gst,
        'discount': discount,
        'grand_total': grand_total,
    }

    return render(
        request,
        'cart/cart.html',
        context
    )


@login_required(login_url='accounts:login')
def update_cart(request, item_id):

    if request.method != 'POST':
        return redirect('cart:view')

    cart = get_user_cart(request)

    # IMPORTANT:
    # Item sirf current logged-in user ke cart se milega.
    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart=cart
    )

    try:
        quantity = int(
            request.POST.get('quantity', 1)
        )
    except (TypeError, ValueError):
        quantity = 1

    if quantity > 0:

        cart_item.quantity = quantity
        cart_item.save()

        messages.success(
            request,
            'Cart updated!'
        )

    else:

        cart_item.delete()

        messages.warning(
            request,
            'Item removed!'
        )

    return redirect('cart:view')


@login_required(login_url='accounts:login')
def remove_from_cart(request, item_id):

    cart = get_user_cart(request)

    # User dusre user ke CartItem ko delete nahi kar sakta
    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart=cart
    )

    cart_item.delete()

    messages.warning(
        request,
        'Item removed from cart!'
    )

    return redirect('cart:view')


@login_required(login_url='accounts:login')
def cart_count(request):

    cart = get_user_cart(request)

    count = 0

    if cart:
        count = cart.get_total_items()

    return JsonResponse({
        'count': count
    })
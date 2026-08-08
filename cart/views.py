from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from books.models import Book
from .models import Cart, CartItem
from decimal import Decimal

def get_or_create_cart(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    return cart

def add_to_cart(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    cart = get_or_create_cart(request)
    quantity = int(request.POST.get('quantity', 1))
    cart_item, created = CartItem.objects.get_or_create(cart=cart, book=book)
    if not created:
        cart_item.quantity += quantity
        cart_item.save()
        messages.success(request, f'"{book.title}" quantity updated!')
    else:
        cart_item.quantity = quantity
        cart_item.save()
        messages.success(request, f'"{book.title}" added to cart!')
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'cart_count': cart.get_total_items(),
            'cart_total': float(cart.get_total_price())
        })
    return redirect(request.META.get('HTTP_REFERER', 'core:home'))

def view_cart(request):
    cart = None
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
    else:
        session_key = request.session.session_key
        if session_key:
            cart = Cart.objects.filter(session_key=session_key).first()
    
    subtotal = Decimal('0')
    delivery_charge = Decimal('0')
    gst = Decimal('0')
    discount = Decimal('0')
    grand_total = Decimal('0')
    
    if cart:
        subtotal = cart.get_total_price()  # Decimal
        delivery_charge = Decimal('0') if subtotal >= 500 else Decimal('50')
        gst = subtotal * Decimal('0.05')
        discount = Decimal('0')
        grand_total = subtotal + delivery_charge + gst - discount
    
    context = {
        'cart': cart,
        'subtotal': subtotal,
        'delivery_charge': delivery_charge,
        'gst': gst,
        'discount': discount,
        'grand_total': grand_total,
    }
    return render(request, 'cart/cart.html', context)

def update_cart(request, item_id):
    if request.method == 'POST':
        cart_item = get_object_or_404(CartItem, id=item_id)
        quantity = int(request.POST.get('quantity', 1))
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
            messages.success(request, 'Cart updated!')
        else:
            cart_item.delete()
            messages.warning(request, 'Item removed!')
    return redirect('cart:view')

def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id)
    cart_item.delete()
    messages.warning(request, 'Item removed from cart!')
    return redirect('cart:view')
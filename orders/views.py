from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.http import Http404
from decimal import Decimal

from cart.models import Cart
from .models import Order, OrderItem, PaymentProof, Address
from .forms import DeliveryDetailsForm, PaymentProofForm


def get_cart(request):
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart = Cart.objects.filter(session_key=session_key).first()
    return cart


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.user != request.user and not request.user.is_staff:
        raise Http404("Order not found.")
    proof = PaymentProof.objects.filter(order=order).first()
    return render(request, 'orders/order_detail.html', {
        'order': order,
        'proof': proof,
    })


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'orders/my_orders.html', {'orders': orders})


@login_required
def checkout_delivery(request):
    cart = get_cart(request)
    if not cart or cart.get_total_items() == 0:
        messages.error(request, 'Your cart is empty.')
        return redirect('books:list')

    initial = {}
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile:
            initial = {
                'full_name': request.user.get_full_name(),
                'email': request.user.email,
                'phone': profile.phone,
                'address': profile.address,
                'city': profile.city,
                'state': profile.state,
                'pincode': profile.pincode,
                'landmark': getattr(profile, 'landmark', ''),
            }
    addresses = Address.objects.filter(user=request.user)

    if request.method == 'POST':
        form = DeliveryDetailsForm(request.POST)
        if form.is_valid():
            request.session['delivery_data'] = form.cleaned_data
            return redirect('orders:payment_method')
    else:
        form = DeliveryDetailsForm(initial=initial)

    return render(request, 'orders/checkout_delivery.html', {
        'form': form,
        'cart': cart,
        'addresses': addresses,
    })


@login_required
def payment_method(request):
    cart = get_cart(request)
    if not cart or cart.get_total_items() == 0:
        messages.error(request, 'Cart is empty.')
        return redirect('books:list')

    if not request.session.get('delivery_data'):
        return redirect('orders:checkout_delivery')

    if request.method == 'POST':
        method = request.POST.get('payment_method')
        valid_methods = dict(Order.PAYMENT_METHODS).keys()
        if method in valid_methods:
            request.session['payment_method'] = method
            return redirect('orders:payment_screen')
        else:
            messages.error(request, 'Please select a valid payment method.')

    methods = dict(Order.PAYMENT_METHODS)
    return render(request, 'orders/payment_method.html', {
        'cart': cart,
        'methods': methods,
    })


@login_required
def payment_screen(request):
    cart = get_cart(request)
    if not cart or cart.get_total_items() == 0:
        return redirect('books:list')

    delivery_data = request.session.get('delivery_data')
    payment_method = request.session.get('payment_method')
    if not delivery_data or not payment_method:
        return redirect('orders:checkout_delivery')

    subtotal = cart.get_total_price()
    delivery_charges = Decimal('0') if subtotal >= Decimal('500') else Decimal('50')
    discount = Decimal('0')
    tax = subtotal * Decimal('0.05')
    grand_total = subtotal + delivery_charges + tax - discount

    # Create order with landmark
    order = Order.objects.create(
        user=request.user,
        full_name=delivery_data['full_name'],
        email=delivery_data['email'],
        phone=delivery_data['phone'],
        address=delivery_data['address'],
        city=delivery_data['city'],
        state=delivery_data['state'],
        pincode=delivery_data['pincode'],
        landmark=delivery_data.get('landmark', ''),  # ✅ landmark included
        total_amount=subtotal,
        delivery_charges=delivery_charges,
        discount=discount,
        tax=tax,
        grand_total=grand_total,
        payment_method=payment_method,
        payment_status='pending',
        order_status='draft',
    )

    for item in cart.items.all():
        OrderItem.objects.create(
            order=order,
            book=item.book,
            quantity=item.quantity,
            price=item.book.final_price
        )
    cart.items.all().delete()
    request.session['order_id'] = order.id

    instructions = {
        'upi': {
            'title': 'UPI',
            'details': 'Pay using UPI ID: surendra@upi',
            'qr': f'https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=upi://pay?pa=surendra@upi&pn=Surendra%20BookStore&am={grand_total}&cu=INR',
        },
        'qr': {
            'title': 'QR Code',
            'details': 'Scan QR code below',
            'qr': f'https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=upi://pay?pa=surendra@upi&pn=Surendra%20BookStore&am={grand_total}&cu=INR',
        },
        'banktransfer': {
            'title': 'Bank Transfer',
            'details': 'Bank: Surendra BookStore\nAccount: 1234567890\nIFSC: XYZB0001234',
        },
        'netbanking': {
            'title': 'Net Banking',
            'details': 'Net banking coming soon. Please use bank transfer or UPI.',
        },
        'cod': {
            'title': 'Cash on Delivery',
            'details': 'Pay when you receive the order.',
        },
    }

    context = {
        'order': order,
        'instructions': instructions.get(payment_method, {}),
        'subtotal': subtotal,
        'delivery_charges': delivery_charges,
        'discount': discount,
        'tax': tax,
        'grand_total': grand_total,
    }
    return render(request, 'orders/payment_screen.html', context)


@login_required
def payment_submit(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.payment_status != 'pending':
        messages.warning(request, 'This order is already processed.')
        return redirect('orders:status', order_id=order.id)

    if request.method == 'POST':
        form = PaymentProofForm(request.POST, request.FILES)
        if form.is_valid():
            proof = form.save(commit=False)
            proof.order = order
            proof.save()
            order.payment_status = 'under_review'
            order.order_status = 'pending'
            order.save()
            messages.success(request, 'Payment proof submitted! Your order is under review.')
            return redirect('orders:status', order_id=order.id)
    else:
        form = PaymentProofForm(initial={'paid_amount': order.grand_total, 'payer_name': order.full_name})

    return render(request, 'orders/payment_submit.html', {
        'form': form,
        'order': order,
    })


@login_required
def order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    proof = PaymentProof.objects.filter(order=order).first()
    return render(request, 'orders/order_status.html', {
        'order': order,
        'proof': proof,
    })


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.payment_status != 'verified' or order.order_status != 'processing':
        messages.warning(request, 'This order is not confirmed yet.')
        return redirect('orders:status', order_id=order.id)
    return render(request, 'orders/order_success.html', {'order': order})


@staff_member_required
def admin_verify_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    proof = get_object_or_404(PaymentProof, order=order)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'verify':
            order.payment_status = 'verified'
            order.order_status = 'processing'
            order.payment_verified_at = timezone.now()
            order.save()
            proof.verified_by = request.user
            proof.verified_at = timezone.now()
            proof.admin_notes = request.POST.get('admin_notes', '')
            proof.save()
            try:
                subject = f'Order #{order.id} Confirmed - Surendra BookStore'
                html_message = render_to_string('emails/order_confirmation.html', {'order': order})
                send_mail(
                    subject,
                    '',
                    settings.DEFAULT_FROM_EMAIL,
                    [order.email],
                    html_message=html_message,
                    fail_silently=False,
                )
            except Exception as e:
                print(e)
            messages.success(request, 'Payment verified and email sent.')
            return redirect('admin:orders_order_changelist')
        elif action == 'reject':
            order.payment_status = 'rejected'
            order.order_status = 'cancelled'
            order.save()
            proof.admin_notes = request.POST.get('admin_notes', '')
            proof.save()
            messages.warning(request, 'Payment rejected.')
            return redirect('admin:orders_order_changelist')
    return render(request, 'orders/admin_verify_payment.html', {'order': order, 'proof': proof})
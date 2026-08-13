from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from cart.models import Cart, Coupon
from core.models import ServiceablePincode
from cart.views import get_session_coupon
from .forms import DeliveryDetailsForm, PaymentProofForm
from .models import Address, Order, OrderItem, OrderEvent, PaymentProof
import json
import urllib.request
import urllib.error

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from cart.models import Cart
from django.db import transaction

# ============================================================
# CART HELPER
# ============================================================

def get_cart(request):
    """
    Return the current user's cart.

    Authenticated users:
        cart is linked to the logged-in user.

    Guest users:
        cart is linked to the current session.

    This function NEVER creates/deletes cart items by itself.
    """

    if request.user.is_authenticated:
        return Cart.objects.filter(user=request.user).first()

    session_key = request.session.session_key

    if not session_key:
        request.session.create()
        session_key = request.session.session_key

    return Cart.objects.filter(session_key=session_key).first()


def _cart_is_available(cart):
    """
    Safe cart availability check.
    """
    return bool(cart and cart.get_total_items() > 0)


def _verified_rajasthan_location(pincode):
    """Authoritatively validate any Rajasthan PIN with India Post at checkout time."""
    if not pincode or not str(pincode).isdigit() or len(str(pincode)) != 6 or str(pincode).startswith("0"):
        return None
    try:
        api_url = f"https://api.postalpincode.in/pincode/{pincode}"
        request_obj = urllib.request.Request(api_url, headers={"User-Agent": "SurendraBookStore/1.0"})
        with urllib.request.urlopen(request_obj, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
        result = data[0] if isinstance(data, list) and data else {}
        offices = result.get("PostOffice") or []
        office = next((item for item in offices if isinstance(item, dict) and item.get("State")), None)
        if not office or str(office.get("State", "")).strip().lower() != "rajasthan":
            return None
        return {"city": str(office.get("District") or office.get("Block") or office.get("Name") or "").strip(), "state": "Rajasthan"}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None


# ============================================================
# CHECKOUT SESSION HELPERS
# ============================================================

def _get_checkout_order(request):
    """
    Return the draft order stored in checkout session.

    Only draft orders belonging to the current user are returned.

    We intentionally do not create an order here.
    """

    order_id = request.session.get("order_id")

    if not order_id:
        return None

    try:
        order = Order.objects.filter(
            id=order_id,
            user=request.user,
        ).first()
    except (TypeError, ValueError):
        return None

    if not order:
        request.session.pop("order_id", None)
        request.session.modified = True
        return None

    # Once an order has moved beyond draft state, don't treat it
    # as the current editable checkout order.
    if order.order_status not in ("draft",):
        request.session.pop("order_id", None)
        request.session.modified = True
        return None

    return order


def _clear_checkout_session(request):
    """
    Remove temporary checkout state.

    Cart is intentionally NOT touched here.
    """

    request.session.pop("delivery_data", None)
    request.session.pop("payment_method", None)
    request.session.pop("order_id", None)
    request.session.modified = True


# ============================================================
# ORDER TOTALS
# ============================================================

def _calculate_totals(cart, coupon=None):
    """
    Calculate checkout totals using the same rules as the cart.

    Rules preserved:
        subtotal < ₹500  => ₹50 delivery
        subtotal >= ₹500 => FREE delivery
        GST               => 5%
        coupon discount   => validated against the live coupon object
    """

    subtotal = Decimal(str(cart.get_total_price() or "0")).quantize(Decimal("0.01"))

    delivery_charges = Decimal("0.00") if subtotal >= Decimal(str(settings.FREE_SHIPPING_MINIMUM)) else Decimal(str(settings.SHIPPING_CHARGE))

    discount = Decimal("0.00")
    if coupon:
        valid, _ = coupon.is_valid(subtotal)
        if valid:
            discount = coupon.calculate_discount(subtotal).quantize(Decimal("0.01"))

    tax = (subtotal * Decimal(str(settings.GST_RATE)) / Decimal("100")).quantize(Decimal("0.01"))

    grand_total = (
        subtotal
        + delivery_charges
        + tax
        - discount
    ).quantize(Decimal("0.01"))

    if grand_total < Decimal("0.00"):
        grand_total = Decimal("0.00")

    return {
        "subtotal": subtotal,
        "delivery_charges": delivery_charges,
        "discount": discount,
        "tax": tax,
        "grand_total": grand_total,
    }


# ============================================================
# PAYMENT INSTRUCTIONS
# ============================================================

def _get_payment_instructions(payment_method, grand_total):
    """
    Existing payment methods are preserved.

    IMPORTANT:
    Payment credentials remain the same as the current project.
    """

    amount = f"{grand_total:.2f}"

    # Keep the existing UPI/business details from the project.
    upi_id = settings.STORE_UPI_ID
    store_name = settings.STORE_UPI_PAYEE

    qr_data = (
        f"upi://pay?"
        f"pa={upi_id}"
        f"&pn={store_name.replace(' ', '%20')}"
        f"&am={amount}"
        f"&cu=INR"
    )

    qr_url = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=250x250&data={qr_data}"
    )

    instructions = {
        "upi": {
            "title": "UPI Payment",
            "details": f"Pay using UPI ID: {upi_id}",
            "qr": qr_url,
        },

        "qr": {
            "title": "QR Code Payment",
            "details": "Scan the QR code below to complete your payment.",
            "qr": qr_url,
        },

        "banktransfer": {
            "title": "Bank Transfer",
            "details": (
                "Account Holder: Surendra Book Store\nBank: Airtel Payments Bank\n"
                "Account Number: 8000411638\nIFSC: AIRP0000001\nBranch: Jalore"
            ),
        },

        "netbanking": {
            "title": "Net Banking",
            "details": (
                "Net banking payment instructions are currently "
                "handled through the available bank transfer option."
            ),
        },

        "cod": {
            "title": "Cash on Delivery",
            "details": (
                "No online payment is required.\n"
                "Pay when your order is delivered."
            ),
        },
    }

    return instructions.get(
        payment_method,
        {
            "title": "Payment",
            "details": "Please follow the payment instructions.",
        },
    )


# ============================================================
# ORDER DETAIL
# ============================================================

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if order.user != request.user and not request.user.is_staff:
        raise Http404("Order not found.")

    proof = PaymentProof.objects.filter(order=order).first()

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "proof": proof,
        },
    )


# ============================================================
# MY ORDERS
# ============================================================

@login_required
def my_orders(request):
    orders = (
        Order.objects
        .filter(user=request.user)
        .order_by("-created_at")
    )

    return render(
        request,
        "orders/my_orders.html",
        {
            "orders": orders,
        },
    )


# ============================================================
# DELIVERY CHECKOUT
# ============================================================

@login_required
def checkout_delivery(request):
    cart = get_cart(request)

    if not _cart_is_available(cart):
        messages.error(request, "Your cart is empty.")
        return redirect("books:list")

    initial = {}

    profile = getattr(request.user, "profile", None)

    if profile:
        initial = {
            "full_name": request.user.get_full_name(),
            "email": request.user.email,
            "phone": getattr(profile, "phone", ""),
            "address": getattr(profile, "address", ""),
            "city": getattr(profile, "city", ""),
            "state": getattr(profile, "state", ""),
            "pincode": getattr(profile, "pincode", ""),
            "landmark": getattr(profile, "landmark", ""),
        }

    # If the user has already entered checkout delivery information,
    # use that instead of resetting the form.
    session_delivery = request.session.get("delivery_data")

    if session_delivery:
        initial.update(session_delivery)

    addresses = Address.objects.filter(
        user=request.user
    ).order_by("-is_default", "-created_at")

    coupon = get_session_coupon(request)

    # Revalidate the coupon against the current cart before rendering
    # checkout. Never trust a stale session discount.
    if coupon:
        subtotal = Decimal(str(cart.get_total_price() or "0"))
        valid, error_message = coupon.is_valid(subtotal)
        if not valid:
            request.session.pop("cart_coupon_code", None)
            request.session.modified = True
            messages.warning(request, "Coupon removed: " + error_message)
            coupon = None

    totals = _calculate_totals(cart, coupon)

    if request.method == "POST":
        form = DeliveryDetailsForm(request.POST, user=request.user)

        if form.is_valid():
            delivery_data = dict(form.cleaned_data)

            # This is the authoritative delivery gate; all verified Rajasthan PIN codes are supported.
            location = _verified_rajasthan_location(delivery_data["pincode"])
            if not location:
                form.add_error("pincode", "Delivery is currently available only for valid Rajasthan pincodes. Please check the PIN and try again.")
                return render(request, "orders/checkout_delivery.html", {"form": form, "cart": cart, "addresses": addresses, **_calculate_totals(cart, coupon)})
            delivery_data["city"] = location["city"]
            delivery_data["state"] = location["state"]

            # Convert values to session-safe primitive values.
            for key, value in list(delivery_data.items()):
                if value is None:
                    delivery_data[key] = ""

            # Never trust a client-supplied email, even though the UI is readonly.
            delivery_data["email"] = request.user.email.strip().lower()

            request.session["delivery_data"] = delivery_data
            request.session.modified = True

            messages.success(
                request,
                "Delivery details saved successfully."
            )

            return redirect("orders:payment_method")

    else:
        # Always force the account email on GET as well.
        initial["email"] = request.user.email
        form = DeliveryDetailsForm(initial=initial, user=request.user)

    return render(
        request,
        "orders/checkout_delivery.html",
        {
            "form": form,
            "cart": cart,
            "addresses": addresses,
            "subtotal": totals["subtotal"],
            "delivery_charges": totals["delivery_charges"],
            "discount": totals["discount"],
            "tax": totals["tax"],
            "grand_total": totals["grand_total"],
            "applied_coupon": coupon,
            "coupon_code": coupon.code if coupon else "",
        },
    )


# ============================================================
# PAYMENT METHOD
# ============================================================

@login_required
def payment_method(request):
    """
    Premium checkout payment-method page.

    IMPORTANT:
    - Does not create an Order.
    - Does not clear the cart.
    - Does not process payment.
    - Only stores the selected payment method in session.
    - Calculates the same checkout totals that the payment screen uses.
    """

    cart = get_cart(request)

    # ---------------------------------------------------------
    # CART VALIDATION
    # ---------------------------------------------------------
    if not cart or cart.get_total_items() == 0:
        messages.error(request, "Your cart is empty.")
        return redirect("books:list")

    # ---------------------------------------------------------
    # DELIVERY VALIDATION
    # ---------------------------------------------------------
    delivery_data = request.session.get("delivery_data")

    if not delivery_data:
        messages.warning(
            request,
            "Please complete your delivery details first."
        )
        return redirect("orders:checkout_delivery")

    # ---------------------------------------------------------
    # SERVER-SIDE TOTAL CALCULATION
    # ---------------------------------------------------------
    subtotal = Decimal(str(cart.get_total_price()))

    # Delivery:
    # ₹50 below ₹500
    # FREE for ₹500+
    delivery_charges = (
        Decimal("0.00")
        if subtotal >= Decimal(str(settings.FREE_SHIPPING_MINIMUM))
        else Decimal(str(settings.SHIPPING_CHARGE))
    )

    # ---------------------------------------------------------
    # COUPON / DISCOUNT
    # ---------------------------------------------------------
    discount = Decimal("0.00")
    coupon_code = request.session.get("cart_coupon_code", "")

    if coupon_code:
        coupon_code = str(coupon_code).strip().upper()

        try:
            coupon = Coupon.objects.get(code=coupon_code)

            valid, error_message = coupon.is_valid(subtotal)

            if valid:
                discount = Decimal(
                    str(coupon.calculate_discount(subtotal))
                )

                # Never allow an invalid discount.
                if discount < Decimal("0.00"):
                    discount = Decimal("0.00")

                if discount > subtotal:
                    discount = subtotal

            else:
                # Coupon is expired / invalid / minimum not met.
                request.session.pop("cart_coupon_code", None)
                request.session.modified = True
                coupon_code = ""

        except Coupon.DoesNotExist:
            request.session.pop("cart_coupon_code", None)
            request.session.modified = True
            coupon_code = ""

    # ---------------------------------------------------------
    # GST
    # ---------------------------------------------------------
    #
    # Keeping the existing project's 5% GST calculation
    # consistent with payment_screen().
    #
    tax = (
        subtotal * Decimal(str(settings.GST_RATE)) / Decimal("100")
    ).quantize(Decimal("0.01"))

    # ---------------------------------------------------------
    # GRAND TOTAL
    # ---------------------------------------------------------
    grand_total = (
        subtotal
        + delivery_charges
        + tax
        - discount
    ).quantize(Decimal("0.01"))

    if grand_total < Decimal("0.00"):
        grand_total = Decimal("0.00")

    # ---------------------------------------------------------
    # POST: SAVE PAYMENT METHOD ONLY
    # ---------------------------------------------------------
    if request.method == "POST":

        method = (
            request.POST.get("payment_method", "")
            .strip()
        )

        valid_methods = {"upi", "qr", "banktransfer"}

        if method in valid_methods:

            # Save only the selected method.
            # Order is NOT created here.
            request.session["payment_method"] = method
            request.session.modified = True

            return redirect("orders:payment_screen")

        messages.error(
            request,
            "Please select a valid payment method."
        )

    # ---------------------------------------------------------
    # AVAILABLE PAYMENT METHODS
    # ---------------------------------------------------------
    methods = {key: label for key, label in Order.PAYMENT_METHODS if key in {"upi", "qr", "banktransfer"}}

    selected_method = request.session.get(
        "payment_method",
        ""
    )

    # ---------------------------------------------------------
    # FINAL TEMPLATE CONTEXT
    # ---------------------------------------------------------
    context = {
        "cart": cart,
        "methods": methods,
        "selected_method": selected_method,

        # IMPORTANT — these were missing before
        "subtotal": subtotal,
        "delivery_charges": delivery_charges,
        "tax": tax,
        "discount": discount,
        "grand_total": grand_total,
        "coupon_code": coupon_code,
    }

    return render(
        request,
        "orders/payment_method.html",
        context
    )

# ============================================================
# PAYMENT SCREEN / ORDER DRAFT
# ============================================================

@login_required
def payment_screen(request):
    cart = get_cart(request)

    if not _cart_is_available(cart):
        messages.error(request, "Your cart is empty.")
        return redirect("books:list")

    delivery_data = request.session.get("delivery_data")
    payment_method = request.session.get("payment_method")

    if not delivery_data:
        messages.warning(
            request,
            "Please complete your delivery information first."
        )
        return redirect("orders:checkout_delivery")

    if not payment_method:
        messages.warning(
            request,
            "Please select a payment method."
        )
        return redirect("orders:payment_method")

    valid_methods = {"upi", "qr", "banktransfer"}

    if payment_method not in valid_methods:
        request.session.pop("payment_method", None)
        request.session.modified = True

        messages.error(
            request,
            "Invalid payment method. Please select again."
        )
        return redirect("orders:payment_method")

    coupon = get_session_coupon(request)
    totals = _calculate_totals(cart, coupon)

    for cart_item in cart.items.select_related("book"):
        if cart_item.quantity > cart_item.book.stock:
            messages.error(request, f"{cart_item.book.title} no longer has the requested quantity in stock.")
            return redirect("cart:view")

    # --------------------------------------------------------
    # REUSE EXISTING DRAFT ORDER
    # --------------------------------------------------------
    #
    # This is the major duplicate-order protection.
    #
    # If the user:
    # Payment Method -> Payment Screen -> Back
    # -> Change Payment Method -> Payment Screen
    #
    # we update the same draft order instead of creating another.
    #

    order = _get_checkout_order(request)

    with transaction.atomic():

        if order:
            # Update the existing draft with the latest delivery
            # and payment information.

            order.full_name = delivery_data["full_name"]
            order.email = delivery_data["email"]
            order.phone = delivery_data["phone"]
            order.address = delivery_data["address"]
            order.city = delivery_data["city"]
            order.state = delivery_data["state"]
            order.pincode = delivery_data["pincode"]
            order.landmark = delivery_data.get("landmark", "")
            order.address_line_2 = delivery_data.get("address_line_2", "")
            order.country = delivery_data.get("country", "India")
            order.delivery_instructions = delivery_data.get("delivery_instructions", "")

            order.total_amount = totals["subtotal"]
            order.delivery_charges = totals["delivery_charges"]
            order.discount = totals["discount"]
            order.tax = totals["tax"]
            order.grand_total = totals["grand_total"]

            order.payment_method = payment_method

            # Keep a draft pending until payment/verification stage.
            order.payment_status = "pending"
            order.order_status = "draft"

            order.save()

            # Synchronize draft items with the current cart.
            #
            # This protects against quantity changes made in the cart
            # before returning to checkout.
            existing_items = {
                item.book_id: item
                for item in order.items.all()
            }

            cart_book_ids = set()

            for cart_item in cart.items.select_related("book").all():
                cart_book_ids.add(cart_item.book_id)

                order_item = existing_items.get(cart_item.book_id)

                if order_item:
                    order_item.quantity = cart_item.quantity
                    order_item.price = cart_item.book.final_price
                    order_item.save(
                        update_fields=["quantity", "price"]
                    )
                else:
                    OrderItem.objects.create(
                        order=order,
                        book=cart_item.book,
                        quantity=cart_item.quantity,
                        price=cart_item.book.final_price,
                    )

            # Remove order items that no longer exist in cart.
            order.items.exclude(
                book_id__in=cart_book_ids
            ).delete()

        else:
            # Create ONLY ONE draft for this checkout session.
            order = Order.objects.create(
                user=request.user,
                full_name=delivery_data["full_name"],
                email=delivery_data["email"],
                phone=delivery_data["phone"],
                address=delivery_data["address"],
                city=delivery_data["city"],
                state=delivery_data["state"],
                pincode=delivery_data["pincode"],
                landmark=delivery_data.get("landmark", ""),
                address_line_2=delivery_data.get("address_line_2", ""),
                country=delivery_data.get("country", "India"),
                delivery_instructions=delivery_data.get("delivery_instructions", ""),

                total_amount=totals["subtotal"],
                delivery_charges=totals["delivery_charges"],
                discount=totals["discount"],
                tax=totals["tax"],
                grand_total=totals["grand_total"],

                payment_method=payment_method,
                payment_status="pending",
                order_status="draft",
            )

            for item in cart.items.select_related("book").all():
                OrderItem.objects.create(
                    order=order,
                    book=item.book,
                    quantity=item.quantity,
                    price=item.book.final_price,
                )

        request.session["order_id"] = order.id
        request.session.modified = True

    # ========================================================
    # COD
    # ========================================================
    #
    # COD does NOT require:
    # - QR
    # - UPI
    # - payment proof
    # - screenshot
    # - UTR
    #
    # Since the current project has no separate COD-submit URL,
    # we finalize the COD checkout here after creating/updating
    # the draft order.
    #
    # Cart is cleared only AFTER the COD order is successfully
    # finalized.
    #

    if payment_method == "cod":

        with transaction.atomic():
            order.payment_status = "verified"
            order.order_status = "pending"
            order.payment_verified_at = timezone.now()
            order.save(
                update_fields=[
                    "payment_status",
                    "order_status",
                    "payment_verified_at",
                    "updated_at",
                ]
            )

            # COD is now a finalized order.
            # This is the first point where cart cleanup is allowed.
            cart.items.all().delete()

            _clear_checkout_session(request)

        messages.success(
            request,
            f"COD order #{order.id} placed successfully."
        )

        return redirect(
            "orders:status",
            order_id=order.id,
        )

    # ========================================================
    # ONLINE PAYMENT
    # ========================================================

    instructions = _get_payment_instructions(
        payment_method,
        totals["grand_total"],
    )

    context = {
        "order": order,
        "instructions": instructions,
        "upi_id": settings.STORE_UPI_ID,
        "bank_account": "8000411638",
        "bank_ifsc": "AIRP0000001",
        "bank_name": "Airtel Payments Bank",

        "subtotal": totals["subtotal"],
        "delivery_charges": totals["delivery_charges"],
        "discount": totals["discount"],
        "tax": totals["tax"],
        "grand_total": totals["grand_total"],
    }

    return render(
        request,
        "orders/payment_screen.html",
        context,
    )


# ============================================================
# PAYMENT PROOF SUBMISSION
# ============================================================

@login_required
def payment_submit(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user,
    )

    # --------------------------------------------------------
    # Security: don't allow payment proof for COD.
    # --------------------------------------------------------

    if order.payment_method == "cod":
        messages.info(
            request,
            "Cash on Delivery does not require payment proof."
        )
        return redirect(
            "orders:status",
            order_id=order.id,
        )

    # Only draft/pending online orders can receive proof.
    if order.order_status not in ("draft", "pending"):
        messages.warning(
            request,
            "This order is no longer accepting payment proof."
        )
        return redirect(
            "orders:status",
            order_id=order.id,
        )

    if order.payment_status != "pending":
        messages.warning(
            request,
            "This order is already being processed."
        )
        return redirect(
            "orders:status",
            order_id=order.id,
        )

    existing_proof = PaymentProof.objects.filter(
        order=order
    ).first()

    if existing_proof:
        messages.info(
            request,
            "Payment proof has already been submitted for this order."
        )
        return redirect(
            "orders:status",
            order_id=order.id,
        )

    if request.method == "POST":

        form = PaymentProofForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():

            proof = form.save(commit=False)

            # ------------------------------------------------
            # Validate amount
            # ------------------------------------------------
            try:
                paid_amount = Decimal(
                    str(proof.paid_amount)
                ).quantize(Decimal("0.01"))
            except (InvalidOperation, TypeError, ValueError):
                form.add_error(
                    "paid_amount",
                    "Please enter a valid payment amount."
                )
                paid_amount = None

            expected_amount = Decimal(
                str(order.grand_total)
            ).quantize(Decimal("0.01"))

            if (
                paid_amount is not None
                and paid_amount != expected_amount
            ):
                form.add_error(
                    "paid_amount",
                    (
                        f"Payment amount must be "
                        f"₹{expected_amount:.2f}."
                    ),
                )

            if form.errors:
                return render(
                    request,
                    "orders/payment_submit.html",
                    {
                        "form": form,
                        "order": order,
                    },
                )

            proof.order = order

            with transaction.atomic():

                # Final duplicate protection.
                if PaymentProof.objects.filter(
                    order=order
                ).exists():
                    messages.info(
                        request,
                        "Payment proof has already been submitted."
                    )
                    return redirect(
                        "orders:status",
                        order_id=order.id,
                    )

                if PaymentProof.objects.filter(utr_number__iexact=proof.utr_number).exists():
                    form.add_error("utr_number", "This UTR / transaction ID was already used.")
                    return render(request, "orders/payment_submit.html", {"form": form, "order": order})
                proof.save()

                order.payment_status = "under_review"
                order.order_status = "pending"
                order.save(
                    update_fields=[
                        "payment_status",
                        "order_status",
                        "updated_at",
                    ]
                )

                # IMPORTANT:
                # Cart is NOT cleared here.
                #
                # Admin must verify the payment first.
                #

            messages.success(
                request,
                (
                    "Payment proof submitted successfully. "
                    "Your order is now under review."
                ),
            )

            return redirect(
                "orders:status",
                order_id=order.id,
            )

    else:
        form = PaymentProofForm(
            initial={
                "paid_amount": order.grand_total,
                "payer_name": order.full_name,
            }
        )

    return render(
        request,
        "orders/payment_submit.html",
        {
            "form": form,
            "order": order,
        },
    )


# ============================================================
# ORDER STATUS
# ============================================================

@login_required
def order_status(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user,
    )

    proof = PaymentProof.objects.filter(
        order=order
    ).first()

    return render(
        request,
        "orders/order_status.html",
        {
            "order": order,
            "proof": proof,
        },
    )


# ============================================================
# ORDER SUCCESS
# ============================================================

@login_required
def order_success(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user,
    )

    if (
        order.payment_status != "verified"
        or order.order_status != "processing"
    ):
        messages.warning(
            request,
            "This order is not confirmed yet."
        )

        return redirect(
            "orders:status",
            order_id=order.id,
        )

    return render(
        request,
        "orders/order_success.html",
        {
            "order": order,
        },
    )


# ============================================================
# ADMIN PAYMENT VERIFICATION
# ============================================================

@staff_member_required
def admin_verify_payment(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
    )

    proof = get_object_or_404(
        PaymentProof,
        order=order,
    )

    if request.method == "POST":

        action = (
            request.POST.get("action") or ""
        ).strip().lower()

        admin_notes = request.POST.get(
            "admin_notes",
            "",
        ).strip()

        # ====================================================
        # VERIFY
        # ====================================================

        if action == "verify":

            with transaction.atomic():

                order.payment_status = "verified"
                order.order_status = "processing"
                order.payment_verified_at = timezone.now()

                if admin_notes:
                    order.admin_notes = admin_notes

                order.save(
                    update_fields=[
                        "payment_status",
                        "order_status",
                        "payment_verified_at",
                        "admin_notes",
                        "updated_at",
                    ]
                )

                proof.verified_by = request.user
                proof.verified_at = timezone.now()
                proof.admin_notes = admin_notes
                proof.save(
                    update_fields=[
                        "verified_by",
                        "verified_at",
                        "admin_notes",
                    ]
                )

                # ------------------------------------------------
                # IMPORTANT:
                # The checkout cart is only cleared after successful
                # admin verification.
                #
                # The current checkout session may no longer have
                # the same cart/session, so we safely resolve the
                # authenticated user's active cart.
                # ------------------------------------------------

                cart = Cart.objects.filter(
                    user=order.user
                ).first()

                if cart:
                    cart.items.all().delete()

                request.session.pop(
                    "order_id",
                    None,
                )
                request.session.pop(
                    "delivery_data",
                    None,
                )
                request.session.pop(
                    "payment_method",
                    None,
                )
                request.session.modified = True

            # ----------------------------------------------------
            # Email should NOT break successful verification.
            # ----------------------------------------------------

            email_sent = False

            try:
                subject = (
                    f"Order #{order.id} Confirmed "
                    f"- Surendra BookStore"
                )

                html_message = render_to_string(
                    "emails/order_confirmation.html",
                    {
                        "order": order,
                    },
                )

                send_mail(
                    subject,
                    "",
                    settings.DEFAULT_FROM_EMAIL,
                    [order.email],
                    html_message=html_message,
                    fail_silently=False,
                )

                email_sent = True

            except Exception as exc:
                # Verification is already successful.
                # Email failure must not roll back the order.
                print(
                    f"Order confirmation email failed "
                    f"for Order #{order.id}: {exc}"
                )

            if email_sent:
                messages.success(
                    request,
                    (
                        f"Order #{order.id} payment verified "
                        "and confirmation email sent."
                    ),
                )
            else:
                messages.success(
                    request,
                    (
                        f"Order #{order.id} payment verified "
                        "successfully."
                    ),
                )

            return redirect(
                "admin:orders_order_changelist"
            )

        # ====================================================
        # REJECT
        # ====================================================

        if action == "reject":

            with transaction.atomic():

                order.payment_status = "rejected"
                order.order_status = "cancelled"

                if admin_notes:
                    order.admin_notes = admin_notes

                order.save(
                    update_fields=[
                        "payment_status",
                        "order_status",
                        "admin_notes",
                        "updated_at",
                    ]
                )

                proof.admin_notes = admin_notes
                proof.save(
                    update_fields=[
                        "admin_notes",
                    ]
                )

            # IMPORTANT:
            # We DO NOT clear the cart on rejection.
            #
            # User may need to retry payment / checkout.
            #

            messages.warning(
                request,
                (
                    f"Payment for Order #{order.id} "
                    "was rejected. The cart has been preserved."
                ),
            )

            return redirect(
                "admin:orders_order_changelist"
            )

        messages.error(
            request,
            "Invalid verification action."
        )

    return render(
        request,
        "orders/admin_verify_payment.html",
        {
            "order": order,
            "proof": proof,
        },
    )
    # ============================================================
# PINCODE LOOKUP
# ============================================================

@login_required
@require_GET
def pincode_lookup(request):
    """
    Secure server-side Indian pincode lookup.

    Frontend:
        GET /orders/checkout/pincode-lookup/?pincode=110001

    Returns:
        {
            "success": true,
            "pincode": "110001",
            "city": "...",
            "state": "...",
            "district": "..."
        }

    The external API is called from the backend so that:
    - no API secret is exposed in JavaScript
    - timeout is controlled
    - malformed responses are handled
    - checkout does not crash when the API is unavailable
    """

    pincode = str(request.GET.get("pincode", "")).strip()

    # --------------------------------------------------------
    # Basic Indian pincode validation
    # --------------------------------------------------------

    if not pincode.isdigit() or len(pincode) != 6:
        return JsonResponse(
            {
                "success": False,
                "error": "Please enter a valid 6-digit Indian pincode."
            },
            status=400,
        )

    # Indian pincodes cannot start with 0.
    if pincode[0] == "0":
        return JsonResponse(
            {
                "success": False,
                "error": "Please enter a valid Indian pincode."
            },
            status=400,
        )

    # --------------------------------------------------------
    # India Post / Postal Pincode API
    # --------------------------------------------------------

    api_url = f"https://api.postalpincode.in/pincode/{pincode}"

    try:
        request_obj = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "SurendraBookStore/1.0"
            },
        )

        with urllib.request.urlopen(
            request_obj,
            timeout=6,
        ) as response:

            raw_data = response.read().decode("utf-8")

        data = json.loads(raw_data)

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Pincode service is temporarily unavailable. "
                    "Please enter your city and state manually."
                ),
                "service_unavailable": True,
            },
            status=503,
        )

    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "We could not verify this pincode right now. "
                    "Please try again."
                ),
                "service_unavailable": True,
            },
            status=503,
        )

    except Exception:
        # Never allow a third-party API failure to crash checkout.
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Pincode verification is temporarily unavailable."
                ),
                "service_unavailable": True,
            },
            status=503,
        )

    # --------------------------------------------------------
    # Validate API response structure
    # --------------------------------------------------------

    if not isinstance(data, list) or not data:
        return JsonResponse(
            {
                "success": False,
                "error": "Pincode not found."
            },
            status=404,
        )

    first_result = data[0]

    if not isinstance(first_result, dict):
        return JsonResponse(
            {
                "success": False,
                "error": "Pincode not found."
            },
            status=404,
        )

    status_text = str(
        first_result.get("Status", "")
    ).strip().lower()

    post_offices = first_result.get("PostOffice")

    if status_text != "success" or not post_offices:
        return JsonResponse(
            {
                "success": False,
                "error": "This pincode was not found."
            },
            status=404,
        )

    # --------------------------------------------------------
    # Find first valid post office
    # --------------------------------------------------------

    post_office = None

    for office in post_offices:

        if not isinstance(office, dict):
            continue

        if (
            office.get("District")
            or office.get("Block")
            or office.get("State")
        ):
            post_office = office
            break

    if not post_office:
        return JsonResponse(
            {
                "success": False,
                "error": "Location information was not available."
            },
            status=404,
        )

    # --------------------------------------------------------
    # Extract location
    # --------------------------------------------------------

    district = str(
        post_office.get("District") or ""
    ).strip()

    block = str(
        post_office.get("Block") or ""
    ).strip()

    state = str(
        post_office.get("State") or ""
    ).strip()

    division = str(
        post_office.get("Division") or ""
    ).strip()

    region = str(
        post_office.get("Region") or ""
    ).strip()

    # Prefer district as city because it is generally the
    # most useful checkout-level location.
    city = district or block or division or region

    if not city or not state:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "City/state information could not be determined "
                    "for this pincode."
                )
            },
            status=404,
        )

    if state.lower() != "rajasthan":
        return JsonResponse({"success": False, "pincode": pincode, "serviceable": False, "error": "This pincode is not currently serviceable."}, status=422)

    return JsonResponse(
        {
            "success": True,
            "pincode": pincode,
            "city": city,
            "state": "Rajasthan",
            "serviceable": True,
            "estimated_delivery_days": 5,
            "district": district,
            "block": block,
            "division": division,
            "region": region,
        }
    )

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from books.models import Book

from .models import Cart, CartItem, Coupon


# =========================================================
# CART HELPERS
# =========================================================

def get_user_cart(request):
    """
    Return only the logged-in user's cart.

    Guest cart creation is intentionally disabled because the
    current project uses authenticated carts.
    """
    if not request.user.is_authenticated:
        return None

    cart, created = Cart.objects.get_or_create(
        user=request.user
    )

    return cart


def get_cart_totals(cart, coupon=None):
    """
    Centralized cart calculation.

    Important:
    Cart subtotal remains the original cart subtotal.
    Coupon discount is calculated separately.

    Returns:
        subtotal
        delivery_charge
        gst
        discount
        grand_total
    """

    subtotal = Decimal("0.00")

    if cart:
        subtotal = Decimal(str(cart.get_total_price()))

    delivery_charge = (
        Decimal("0.00")
        if subtotal >= Decimal("500.00")
        else Decimal("50.00")
    )

    gst = subtotal * Decimal("0.05")

    discount = Decimal("0.00")

    if coupon:
        discount = coupon.calculate_discount(subtotal)

    grand_total = (
        subtotal
        + delivery_charge
        + gst
        - discount
    )

    # Absolute safety.
    if grand_total < Decimal("0.00"):
        grand_total = Decimal("0.00")

    return {
        "subtotal": subtotal,
        "delivery_charge": delivery_charge,
        "gst": gst,
        "discount": discount,
        "grand_total": grand_total,
    }


def get_session_coupon(request):
    """
    Get currently applied coupon from session.

    Only the coupon CODE is stored in session.
    The actual Coupon object is fetched from DB every time.

    This prevents stale discount values from being trusted.
    """

    code = request.session.get("cart_coupon_code")

    if not code:
        return None

    code = str(code).strip().upper()

    if not code:
        return None

    try:
        return Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        # Remove stale/invalid session coupon.
        request.session.pop("cart_coupon_code", None)
        request.session.modified = True
        return None


def clear_session_coupon(request):
    """
    Safely remove currently applied coupon.
    """

    if "cart_coupon_code" in request.session:
        request.session.pop("cart_coupon_code", None)
        request.session.modified = True


# =========================================================
# ADD TO CART
# =========================================================

@login_required(login_url="accounts:login")
def add_to_cart(request, book_id):

    book = get_object_or_404(
        Book,
        id=book_id
    )

    cart = get_user_cart(request)

    if cart is None:
        return redirect("accounts:login")

    try:
        quantity = int(
            request.POST.get(
                "quantity",
                1
            )
        )
    except (TypeError, ValueError):
        quantity = 1

    quantity = max(
        quantity,
        1
    )

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        book=book
    )

    if created:
        cart_item.quantity = quantity
        cart_item.save()

        message = (
            f'"{book.title}" added to cart!'
        )

    else:
        cart_item.quantity += quantity
        cart_item.save()

        message = (
            f'"{book.title}" quantity updated!'
        )

    messages.success(
        request,
        message
    )

    if request.headers.get(
        "x-requested-with"
    ) == "XMLHttpRequest":

        return JsonResponse({
            "status": "success",
            "cart_count": cart.get_total_items(),
            "cart_total": float(
                cart.get_total_price()
            ),
            "message": message,
        })

    return redirect(
        request.META.get(
            "HTTP_REFERER",
            "core:home"
        )
    )


# =========================================================
# VIEW CART
# =========================================================

@login_required(login_url="accounts:login")
def view_cart(request):

    cart = get_user_cart(request)

    coupon = get_session_coupon(request)

    # -----------------------------------------------------
    # Validate session coupon every time cart is opened.
    # -----------------------------------------------------

    if coupon and cart:

        subtotal = Decimal(
            str(cart.get_total_price())
        )

        valid, error_message = coupon.is_valid(
            subtotal
        )

        if not valid:

            clear_session_coupon(request)

            messages.warning(
                request,
                error_message
            )

            coupon = None

    totals = get_cart_totals(
        cart,
        coupon
    )

    context = {
        "cart": cart,

        "subtotal": totals["subtotal"],
        "delivery_charge": totals["delivery_charge"],
        "gst": totals["gst"],
        "discount": totals["discount"],
        "grand_total": totals["grand_total"],

        "applied_coupon": coupon,

        "coupon_code": (
            coupon.code
            if coupon
            else ""
        ),
    }

    return render(
        request,
        "cart/cart.html",
        context
    )


# =========================================================
# APPLY COUPON
# =========================================================

@login_required(login_url="accounts:login")
@require_POST
def apply_coupon(request):

    cart = get_user_cart(request)

    if not cart:
        return JsonResponse(
            {
                "status": "error",
                "message": "Your cart is empty.",
            },
            status=400
        )

    if cart.get_total_items() <= 0:
        return JsonResponse(
            {
                "status": "error",
                "message": "Your cart is empty.",
            },
            status=400
        )

    raw_code = request.POST.get(
        "coupon_code",
        ""
    )

    code = str(raw_code).strip().upper()

    if not code:

        return JsonResponse(
            {
                "status": "error",
                "message": "Please enter a coupon code.",
            },
            status=400
        )

    # -----------------------------------------------------
    # Find coupon
    # -----------------------------------------------------

    try:
        coupon = Coupon.objects.get(
            code=code
        )
    except Coupon.DoesNotExist:

        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid coupon code.",
            },
            status=404
        )

    # -----------------------------------------------------
    # Validate coupon
    # -----------------------------------------------------

    subtotal = Decimal(
        str(cart.get_total_price())
    )

    valid, error_message = coupon.is_valid(
        subtotal
    )

    if not valid:

        return JsonResponse(
            {
                "status": "error",
                "message": error_message,
            },
            status=400
        )

    # -----------------------------------------------------
    # Calculate discount
    # -----------------------------------------------------

    discount = coupon.calculate_discount(
        subtotal
    )

    if discount <= Decimal("0.00"):

        return JsonResponse(
            {
                "status": "error",
                "message": "This coupon does not provide a discount for this cart.",
            },
            status=400
        )

    # -----------------------------------------------------
    # Save ONLY coupon code in session.
    # -----------------------------------------------------

    request.session["cart_coupon_code"] = coupon.code
    request.session.modified = True

    totals = get_cart_totals(
        cart,
        coupon
    )

    return JsonResponse({
        "status": "success",
        "message": (
            f"Coupon {coupon.code} applied successfully."
        ),

        "coupon": {
            "code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": str(
                coupon.discount_value
            ),
        },

        "subtotal": str(
            totals["subtotal"]
        ),

        "delivery_charge": str(
            totals["delivery_charge"]
        ),

        "gst": str(
            totals["gst"]
        ),

        "discount": str(
            totals["discount"]
        ),

        "grand_total": str(
            totals["grand_total"]
        ),
    })


# =========================================================
# REMOVE COUPON
# =========================================================

@login_required(login_url="accounts:login")
@require_POST
def remove_coupon(request):

    coupon = get_session_coupon(request)

    if not coupon:

        return JsonResponse({
            "status": "success",
            "message": "No coupon is currently applied.",
        })

    code = coupon.code

    clear_session_coupon(request)

    cart = get_user_cart(request)

    totals = get_cart_totals(
        cart,
        None
    )

    return JsonResponse({
        "status": "success",
        "message": (
            f"Coupon {code} removed."
        ),

        "subtotal": str(
            totals["subtotal"]
        ),

        "delivery_charge": str(
            totals["delivery_charge"]
        ),

        "gst": str(
            totals["gst"]
        ),

        "discount": "0.00",

        "grand_total": str(
            totals["grand_total"]
        ),
    })


# =========================================================
# UPDATE CART
# =========================================================

@login_required(login_url="accounts:login")
@require_POST
def update_cart(request, item_id):

    cart = get_user_cart(request)

    if not cart:
        messages.error(
            request,
            "Cart not found."
        )
        return redirect("cart:view")

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart=cart
    )

    try:
        quantity = int(
            request.POST.get(
                "quantity",
                1
            )
        )
    except (TypeError, ValueError):
        quantity = 1

    if quantity > 0:

        cart_item.quantity = quantity
        cart_item.save()

        messages.success(
            request,
            "Cart updated successfully."
        )

    else:

        cart_item.delete()

        messages.warning(
            request,
            "Item removed from cart."
        )

    # -----------------------------------------------------
    # Revalidate coupon after cart quantity changes.
    # -----------------------------------------------------

    coupon = get_session_coupon(request)

    if coupon:

        subtotal = Decimal(
            str(cart.get_total_price())
        )

        valid, error_message = coupon.is_valid(
            subtotal
        )

        if not valid:

            clear_session_coupon(request)

            messages.warning(
                request,
                (
                    f"Coupon removed: "
                    f"{error_message}"
                )
            )

    return redirect(
        "cart:view"
    )


# =========================================================
# REMOVE FROM CART
# =========================================================

@login_required(login_url="accounts:login")
def remove_from_cart(request, item_id):

    cart = get_user_cart(request)

    if not cart:
        messages.error(
            request,
            "Cart not found."
        )
        return redirect("cart:view")

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart=cart
    )

    cart_item.delete()

    messages.warning(
        request,
        "Item removed from cart."
    )

    # -----------------------------------------------------
    # Revalidate applied coupon after item removal.
    # -----------------------------------------------------

    coupon = get_session_coupon(request)

    if coupon:

        subtotal = Decimal(
            str(cart.get_total_price())
        )

        valid, error_message = coupon.is_valid(
            subtotal
        )

        if not valid:

            clear_session_coupon(request)

            messages.warning(
                request,
                (
                    f"Coupon removed: "
                    f"{error_message}"
                )
            )

    return redirect(
        "cart:view"
    )


# =========================================================
# CART COUNT
# =========================================================

@login_required(login_url="accounts:login")
def cart_count(request):

    cart = get_user_cart(request)

    count = 0

    if cart:
        count = cart.get_total_items()

    return JsonResponse({
        "count": count
    })
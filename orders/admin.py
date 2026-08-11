from django.conf import settings
from django.contrib import admin, messages
from django.core.mail import EmailMessage
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import path
from django.utils import timezone
import re
from .models import Order, OrderItem, PaymentProof, Address

# ============================================================
# EMAIL CLEANER
# ============================================================

def clean_customer_email(email):
    """
    Converts accidental Markdown/mailto email values
    into a normal email address.

    Example:
        [abc@gmail.com](mailto:abc@gmail.com)
        ->
        abc@gmail.com
    """

    if not email:
        raise ValueError("Customer email is empty.")

    email = str(email).strip()

    # Markdown mailto format
    match = re.search(
        r'\[([^\]]+@[^\]]+)\]\(mailto:[^)]+\)',
        email,
        re.IGNORECASE,
    )

    if match:
        email = match.group(1).strip()

    # Plain mailto:
    if email.lower().startswith("mailto:"):
        email = email[7:].strip()

    # Remove accidental surrounding brackets
    email = email.strip("[]()<> ")

    # Basic validation
    if not re.match(
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        email,
    ):
        raise ValueError(
            f"Invalid customer email: {email}"
        )

    return email
# ============================================================
# INVOICE CONTEXT
# ============================================================

def get_invoice_context(order):
    """
    Central invoice context.

    Used by:
        1. Browser invoice
        2. Email invoice
    """

    items = (
        order.items
        .select_related("book")
        .all()
    )

    return {
        "order": order,
        "items": items,
        "total_items": order.get_total_items(),

        "invoice_no": f"INV-{order.id:06d}",

        "date": timezone.localtime(
            order.created_at
        ).strftime("%d %B %Y"),

        "generated_at": timezone.localtime(
            timezone.now()
        ).strftime("%d %B %Y, %I:%M %p"),
    }


# ============================================================
# INVOICE HTML
# ============================================================

def generate_invoice_html(order):
    """
    Generate luxury invoice HTML.
    """

    context = get_invoice_context(order)

    return render_to_string(
        "orders/invoice.html",
        context,
    )


# ============================================================
# PDF
# ============================================================

def generate_invoice_pdf(order):
    """
    PDF generation is intentionally disabled for now.

    WeasyPrint on Windows requires GTK/Pango/Cairo native
    libraries which are currently missing from the system.

    We will add a Chrome/Chromium based PDF solution later.
    """

    raise RuntimeError(
        "PDF generation is temporarily unavailable. "
        "Invoice HTML and email are working normally. "
        "PDF will be generated using the browser-based "
        "PDF engine."
    )


# ============================================================
# SEND ORDER CONFIRMATION EMAIL
# ============================================================

def send_order_confirmation_email(order):
    """
    Send order confirmation ONLY to the email address
    of the logged-in Django user attached to this order.

    Never trust order.email because customer checkout
    form me koi bhi email enter kar sakta hai.
    """

    # --------------------------------------------------------
    # CHECK USER
    # --------------------------------------------------------

    if not order.user:
        raise ValueError(
            f"Order #{order.id} is not linked to a user account."
        )

    # --------------------------------------------------------
    # GET LOGIN ACCOUNT EMAIL
    # --------------------------------------------------------

    customer_email = (
        order.user.email or ""
    ).strip().lower()

    if not customer_email:
        raise ValueError(
            f"User account for Order #{order.id} "
            f"does not have an email address."
        )

    # --------------------------------------------------------
    # CONTEXT
    # --------------------------------------------------------

    context = get_invoice_context(order)

    # IMPORTANT:
    # This must be a REAL HTML EMAIL TEMPLATE.
    html_message = render_to_string(
        "emails/order_confirmation_with_invoice.html",
        context,
    )

    # --------------------------------------------------------
    # EMAIL
    # --------------------------------------------------------

    email = EmailMessage(
        subject=(
            f"Order #{order.id} Confirmed • "
            f"SurendraBookStore"
        ),

        body=html_message,

        from_email=settings.DEFAULT_FROM_EMAIL,

        # VERY IMPORTANT:
        # Never use order.email here.
        # Always use logged-in user's account email.
        to=[
            customer_email,
        ],

        reply_to=[
            settings.DEFAULT_FROM_EMAIL,
        ],
    )

    email.content_subtype = "html"

    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    sent = email.send(
        fail_silently=False
    )

    if sent != 1:
        raise RuntimeError(
            f"Email backend returned {sent}."
        )

    return True

# ============================================================
# VERIFY PAYMENT ACTION
# ============================================================

@admin.action(
    description=(
        "✅ Verify Payment • Send Luxury Invoice Email"
    )
)
def verify_payment_action(
    modeladmin,
    request,
    queryset,
):

    verified_count = 0
    email_failed_count = 0

    for order in queryset:

        # ----------------------------------------------------
        # SECURITY
        # ----------------------------------------------------

        if order.payment_status not in (
            "under_review",
            "pending",
        ):
            continue

        # ----------------------------------------------------
        # VERIFY PAYMENT
        # ----------------------------------------------------

        order.payment_status = "verified"

        order.order_status = "processing"

        order.payment_verified_at = (
            timezone.now()
        )

        order.save(
            update_fields=[
                "payment_status",
                "order_status",
                "payment_verified_at",
                "updated_at",
            ]
        )

        verified_count += 1

        # ----------------------------------------------------
        # SEND EMAIL
        # ----------------------------------------------------

        try:

            send_order_confirmation_email(
                order
            )

        except Exception as exc:

            email_failed_count += 1

            print(
                "\n"
                "================================================\n"
                f"INVOICE EMAIL FAILED - ORDER #{order.id}\n"
                "================================================\n"
                f"Customer Email : {order.email}\n"
                f"Error          : {exc}\n"
                "================================================\n"
            )

    # --------------------------------------------------------
    # ADMIN MESSAGE
    # --------------------------------------------------------

    if email_failed_count:

        modeladmin.message_user(
            request,
            (
                f"{verified_count} order(s) verified. "
                f"{email_failed_count} email(s) failed. "
                f"Check the terminal for the exact error."
            ),
            level=messages.WARNING,
        )

    else:

        modeladmin.message_user(
            request,
            (
                f"{verified_count} order(s) verified "
                f"successfully. "
                f"Luxury confirmation email sent."
            ),
            level=messages.SUCCESS,
        )


# ============================================================
# ORDER ITEM INLINE
# ============================================================

class OrderItemInline(
    admin.TabularInline
):

    model = OrderItem

    extra = 0

    readonly_fields = (
        "book",
        "quantity",
        "price",
        "get_total",
    )

    fields = (
        "book",
        "quantity",
        "price",
        "get_total",
    )

    ordering = (
        "-id",
    )

    @admin.display(
        description="Total"
    )
    def get_total(
        self,
        obj,
    ):

        if (
            obj.price is not None
            and obj.quantity is not None
        ):
            return (
                obj.price
                * obj.quantity
            )

        return 0


# ============================================================
# PAYMENT PROOF INLINE
# ============================================================

class PaymentProofInline(
    admin.StackedInline
):

    model = PaymentProof

    extra = 0

    readonly_fields = (
        "submitted_at",
    )

    fields = (
        "payer_name",
        "paid_amount",
        "utr_number",
        "payment_date",
        "screenshot",
        "notes",
        "submitted_at",
    )


# ============================================================
# ORDER ADMIN
# ============================================================

@admin.register(Order)
class OrderAdmin(
    admin.ModelAdmin
):

    list_display = (
        "id",
        "full_name",
        "email",
        "phone",
        "grand_total",
        "payment_status",
        "order_status",
        "created_at",
    )

    list_filter = (
        "payment_status",
        "order_status",
        "payment_method",
    )

    search_fields = (
        "id",
        "full_name",
        "email",
        "phone",
        "utr_number",
    )

    inlines = [
        OrderItemInline,
        PaymentProofInline,
    ]

    actions = [
        verify_payment_action,
    ]

    readonly_fields = (
        "created_at",
        "updated_at",
        "payment_verified_at",
    )

    list_per_page = 20

    # ========================================================
    # CUSTOM ADMIN URLS
    # ========================================================

    def get_urls(self):

        urls = super().get_urls()

        custom_urls = [

            path(
                "verify/<int:order_id>/",
                self.admin_site.admin_view(
                    self.verify_order
                ),
                name="verify_order",
            ),

            path(
                "invoice/<int:order_id>/",
                self.admin_site.admin_view(
                    self.view_invoice
                ),
                name="view_invoice",
            ),

            path(
                "invoice-html/<int:order_id>/",
                self.admin_site.admin_view(
                    self.download_invoice_html
                ),
                name="download_invoice_html",
            ),

        ]

        return custom_urls + urls

    # ========================================================
    # VERIFY SINGLE ORDER
    # ========================================================

    def verify_order(
        self,
        request,
        order_id,
    ):

        order = get_object_or_404(
            Order,
            id=order_id,
        )

        # ----------------------------------------------------
        # SECURITY
        # ----------------------------------------------------

        if order.payment_status not in (
            "under_review",
            "pending",
        ):

            messages.warning(
                request,
                (
                    "This order has already been "
                    "processed and cannot be verified again."
                ),
            )

            return redirect(
                "admin:orders_order_changelist"
            )

        # ----------------------------------------------------
        # VERIFY
        # ----------------------------------------------------

        order.payment_status = "verified"

        order.order_status = "processing"

        order.payment_verified_at = (
            timezone.now()
        )

        order.save(
            update_fields=[
                "payment_status",
                "order_status",
                "payment_verified_at",
                "updated_at",
            ]
        )

        # ----------------------------------------------------
        # SEND EMAIL
        # ----------------------------------------------------

        try:

            send_order_confirmation_email(
                order
            )

            messages.success(
                request,
                (
                    f"Order #{order.id} verified successfully. "
                    f"Luxury confirmation email sent to "
                    f"{order.email}."
                ),
            )

        except Exception as exc:

            print(
                "\n"
                "================================================\n"
                f"EMAIL FAILED - ORDER #{order.id}\n"
                "================================================\n"
                f"Email : {order.email}\n"
                f"Error : {exc}\n"
                "================================================\n"
            )

            messages.warning(
                request,
                (
                    f"Order #{order.id} was verified, "
                    f"but the email could not be sent. "
                    f"Check the terminal for the exact error."
                ),
            )

        return redirect(
            "admin:orders_order_changelist"
        )

    # ========================================================
    # BROWSER INVOICE PREVIEW
    # ========================================================

    def view_invoice(
        self,
        request,
        order_id,
    ):

        order = get_object_or_404(
            Order,
            id=order_id,
        )

        html = generate_invoice_html(
            order
        )

        return HttpResponse(
            html
        )

    # ========================================================
    # DOWNLOAD HTML INVOICE
    # ========================================================

    def download_invoice_html(
        self,
        request,
        order_id,
    ):

        order = get_object_or_404(
            Order,
            id=order_id,
        )

        html = generate_invoice_html(
            order
        )

        invoice_no = (
            f"INV-{order.id:06d}"
        )

        response = HttpResponse(
            html,
            content_type="text/html; charset=utf-8",
        )

        response[
            "Content-Disposition"
        ] = (
            f'attachment; '
            f'filename="{invoice_no}.html"'
        )

        return response


# ============================================================
# ADDRESS
# ============================================================

admin.site.register(
    Address
)
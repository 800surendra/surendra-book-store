from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from io import BytesIO
import base64
from .models import Order, OrderItem, PaymentProof, Address

# Invoice generation (simple HTML to PDF)
def generate_invoice_html(order):
    items = order.items.all()
    context = {
        'order': order,
        'items': items,
        'total_items': order.get_total_items(),
        'invoice_no': f"INV-{order.id:06d}",
        'date': order.created_at.strftime("%d %B %Y"),
    }
    return render_to_string('orders/invoice.html', context)

@admin.action(description='✅ Verify Payment, Send Email & Invoice')
def verify_payment_action(modeladmin, request, queryset):
    verified_count = 0
    for order in queryset:
        if order.payment_status == 'under_review' or order.payment_status == 'pending':
            order.payment_status = 'verified'
            order.order_status = 'processing'
            order.payment_verified_at = timezone.now()
            order.save()

            # Generate invoice
            invoice_html = generate_invoice_html(order)
            invoice_pdf = None  # You can integrate PDF library later

            # Send email with invoice
            try:
                subject = f'🎉 Order #{order.id} Confirmed - Surendra BookStore'
                html_message = render_to_string('emails/order_confirmation_with_invoice.html', {
                    'order': order,
                    'invoice_html': invoice_html,
                })
                send_mail(
                    subject,
                    '',
                    settings.DEFAULT_FROM_EMAIL,
                    [order.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                verified_count += 1
            except Exception as e:
                print(f"Email failed: {e}")
    modeladmin.message_user(request, f'{verified_count} orders verified and emails sent with invoice.')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('book', 'quantity', 'price', 'get_total')
    fields = ('book', 'quantity', 'price', 'get_total')
    ordering = ('-id',)

    def get_total(self, obj):
        if obj.price is not None and obj.quantity is not None:
            return obj.price * obj.quantity
        return 0
    get_total.short_description = 'Total'

class PaymentProofInline(admin.StackedInline):
    model = PaymentProof
    extra = 0
    readonly_fields = ('submitted_at',)
    fields = ('payer_name', 'paid_amount', 'utr_number', 'payment_date', 'screenshot', 'notes', 'submitted_at')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'email', 'phone', 'grand_total', 'payment_status', 'order_status', 'created_at')
    list_filter = ('payment_status', 'order_status', 'payment_method')
    search_fields = ('id', 'full_name', 'email', 'phone', 'utr_number')
    inlines = [OrderItemInline, PaymentProofInline]
    actions = [verify_payment_action]
    readonly_fields = ('created_at', 'updated_at', 'payment_verified_at')
    list_per_page = 20

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('verify/<int:order_id>/', self.admin_site.admin_view(self.verify_order), name='verify_order'),
            path('invoice/<int:order_id>/', self.admin_site.admin_view(self.view_invoice), name='view_invoice'),
        ]
        return custom_urls + urls

    def verify_order(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        if order.payment_status == 'under_review' or order.payment_status == 'pending':
            order.payment_status = 'verified'
            order.order_status = 'processing'
            order.payment_verified_at = timezone.now()
            order.save()

            try:
                subject = f'🎉 Order #{order.id} Confirmed - Surendra BookStore'
                html_message = render_to_string('emails/order_confirmation_with_invoice.html', {
                    'order': order,
                    'invoice_html': generate_invoice_html(order),
                })
                send_mail(
                    subject,
                    '',
                    settings.DEFAULT_FROM_EMAIL,
                    [order.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                messages.success(request, f'Order #{order.id} verified and email sent with invoice.')
            except Exception as e:
                messages.error(request, f'Email failed: {e}')
        else:
            messages.warning(request, 'This order is already processed.')
        return redirect('admin:orders_order_changelist')

    def view_invoice(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        html = generate_invoice_html(order)
        return HttpResponse(html)

admin.site.register(Address)
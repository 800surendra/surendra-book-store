from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from books.models import Book
from decimal import Decimal

User = get_user_model()

class Order(models.Model):
    PAYMENT_METHODS = (
        ('upi', 'UPI'),
        ('qr', 'QR Code'),
        ('netbanking', 'Net Banking'),
        ('banktransfer', 'Bank Transfer'),
        ('cod', 'Cash on Delivery'),
    )
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('failed', 'Failed'),
    )
    ORDER_STATUS = (
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    landmark = models.CharField(max_length=100, blank=True, null=True)

    # Financial fields
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='upi')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS, default='draft')

    admin_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.full_name}"

    def get_total_items(self):
        return sum(item.quantity for item in self.items.all())


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def get_total(self):
        # Safe calculation (though fields are non‑nullable, this prevents admin errors)
        if self.price is not None and self.quantity is not None:
            return self.price * self.quantity
        return Decimal('0.00')

    def __str__(self):
        return f"{self.quantity} x {self.book.title}"


class PaymentProof(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment_proof')
    payer_name = models.CharField(max_length=200)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2)
    utr_number = models.CharField(max_length=100)
    payment_date = models.DateTimeField()
    screenshot = models.ImageField(upload_to='payment_proofs/', blank=True, null=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    admin_notes = models.TextField(blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_payments')
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Proof for Order #{self.order.id} - {self.utr_number}"


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    landmark = models.CharField(max_length=100, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.city}"
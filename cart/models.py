from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone

from books.models import Book


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart",
    )

    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_total_price(self):
        """
        Existing cart subtotal calculation.
        Coupon/discount is intentionally NOT included here.
        """
        return sum(
            (item.get_total_price() for item in self.items.all()),
            Decimal("0.00"),
        )

    def get_total_items(self):
        """
        Total number of books/items in the cart.
        """
        return sum(
            item.quantity for item in self.items.all()
        )

    def __str__(self):
        owner = self.user or self.session_key or "Guest"
        return f"Cart #{self.id} - {owner}"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
    )

    quantity = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
        ],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "book"],
                name="unique_book_per_cart",
            ),
        ]

    def get_total_price(self):
        """
        Current book price × quantity.
        """
        if not self.book or self.quantity is None:
            return Decimal("0.00")

        price = self.book.final_price or Decimal("0.00")

        return Decimal(price) * self.quantity

    def __str__(self):
        book_title = self.book.title if self.book_id else "Unknown Book"
        return f"{self.quantity} x {book_title}"


class Coupon(models.Model):
    """
    Production-ready coupon configuration.

    Discount itself is NOT permanently stored against the cart.
    The coupon is validated at checkout time so that expired/
    inactive coupons cannot accidentally continue giving discounts.
    """

    DISCOUNT_PERCENTAGE = "percentage"
    DISCOUNT_FIXED = "fixed"

    DISCOUNT_TYPES = (
        (DISCOUNT_PERCENTAGE, "Percentage"),
        (DISCOUNT_FIXED, "Fixed Amount"),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Customer-facing coupon code.",
    )

    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPES,
        default=DISCOUNT_PERCENTAGE,
    )

    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
        help_text="Percentage value or fixed discount amount.",
    )

    minimum_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
        help_text="Minimum cart subtotal required to use this coupon.",
    )

    maximum_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
        help_text=(
            "Optional maximum discount amount for percentage coupons."
        ),
    )

    valid_from = models.DateTimeField(
        null=True,
        blank=True,
    )

    valid_until = models.DateTimeField(
        null=True,
        blank=True,
    )

    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum total number of successful uses. Blank = unlimited.",
    )

    used_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Number of successful uses.",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        """
        Normalize coupon codes so:
        SAVE10
        save10
        Save10

        are treated as the same coupon.
        """
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def is_valid(self, subtotal=None):
        """
        Check whether the coupon can currently be used.

        Returns:
            tuple[bool, str]
        """
        now = timezone.now()

        if not self.is_active:
            return False, "This coupon is currently inactive."

        if self.valid_from and now < self.valid_from:
            return False, "This coupon is not active yet."

        if self.valid_until and now > self.valid_until:
            return False, "This coupon has expired."

        if (
            self.usage_limit is not None
            and self.used_count >= self.usage_limit
        ):
            return False, "This coupon usage limit has been reached."

        if subtotal is not None:
            subtotal = Decimal(str(subtotal))

            if subtotal < self.minimum_order_value:
                return (
                    False,
                    (
                        f"Minimum order value of "
                        f"₹{self.minimum_order_value:.2f} "
                        f"is required for this coupon."
                    ),
                )

        return True, ""

    def calculate_discount(self, subtotal):
        """
        Calculate the actual discount amount.

        Safety rules:
        - Never return a negative discount.
        - Never discount more than the subtotal.
        - Percentage coupons can have an optional maximum cap.
        """
        subtotal = Decimal(str(subtotal))

        if subtotal <= Decimal("0.00"):
            return Decimal("0.00")

        valid, _ = self.is_valid(subtotal)

        if not valid:
            return Decimal("0.00")

        value = Decimal(self.discount_value)

        if self.discount_type == self.DISCOUNT_PERCENTAGE:
            discount = subtotal * value / Decimal("100")

            if self.maximum_discount is not None:
                discount = min(
                    discount,
                    Decimal(self.maximum_discount),
                )

        else:
            discount = value

        discount = max(
            Decimal("0.00"),
            discount,
        )

        return min(
            discount,
            subtotal,
        )

    def mark_used(self):
        """
        Mark one successful coupon usage.

        The actual order/checkout flow will call this only after
        successful final order submission.
        """
        if self.usage_limit is not None:
            if self.used_count >= self.usage_limit:
                return False

        self.used_count += 1

        self.save(
            update_fields=[
                "used_count",
                "updated_at",
            ]
        )

        return True

    @property
    def is_expired(self):
        if not self.valid_until:
            return False

        return timezone.now() > self.valid_until

    def __str__(self):
        if self.discount_type == self.DISCOUNT_PERCENTAGE:
            discount_display = f"{self.discount_value}%"
        else:
            discount_display = f"₹{self.discount_value}"

        return f"{self.code} — {discount_display}"
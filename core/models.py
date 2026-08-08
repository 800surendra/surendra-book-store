from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


PINCODE_VALIDATOR = RegexValidator(
    regex=r"^[1-9]\d{5}$",
    message="Enter a valid 6-digit Indian PIN code.",
)


class ServiceablePincode(models.Model):
    """Delivery policy for a single Indian PIN code."""

    pincode = models.CharField(
        max_length=6,
        unique=True,
        validators=[PINCODE_VALIDATOR],
    )
    area_name = models.CharField(max_length=150, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)

    is_serviceable = models.BooleanField(default=True)
    cash_on_delivery_available = models.BooleanField(default=False)

    estimated_delivery_days = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1)],
    )
    shipping_charge = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    free_shipping_minimum_order = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("999.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("state", "city", "pincode")
        verbose_name = "Serviceable PIN code"
        verbose_name_plural = "Serviceable PIN codes"

    def __str__(self):
        return f"{self.pincode} — {self.city}, {self.state}"
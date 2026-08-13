import re

from django import forms

from .models import Order, PaymentProof, Address


class DeliveryDetailsForm(forms.ModelForm):
    """Secure delivery form used only by the logged-in checkout flow."""

    class Meta:
        model = Order
        fields = [
            "full_name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "pincode",
            "landmark",
            "address_line_2",
            "country",
            "delivery_instructions",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={
                "class": "lux-input",
                "autocomplete": "name",
                "maxlength": 200,
            }),
            "email": forms.EmailInput(attrs={
                "class": "lux-input",
                "autocomplete": "email",
                "readonly": True,
            }),
            "phone": forms.TextInput(attrs={
                "class": "lux-input",
                "autocomplete": "tel",
                "inputmode": "numeric",
                "maxlength": 15,
            }),
            "address": forms.Textarea(attrs={
                "class": "lux-input",
                "rows": 4,
                "autocomplete": "street-address",
                "maxlength": 1000,
            }),
            "city": forms.TextInput(attrs={
                "class": "lux-input",
                "autocomplete": "address-level2",
                "maxlength": 100,
            }),
            "state": forms.TextInput(attrs={
                "class": "lux-input",
                "autocomplete": "address-level1",
                "maxlength": 100,
            }),
            "pincode": forms.TextInput(attrs={
                "class": "lux-input",
                "autocomplete": "postal-code",
                "inputmode": "numeric",
                "maxlength": 6,
                "pattern": r"[1-9][0-9]{5}",
            }),
            "landmark": forms.TextInput(attrs={
                "class": "lux-input",
                "autocomplete": "address-line2",
                "maxlength": 100,
            }),
            "address_line_2": forms.TextInput(attrs={"class": "lux-input", "autocomplete": "address-line2", "maxlength": 200}),
            "country": forms.TextInput(attrs={"class": "lux-input", "value": "India", "maxlength": 100}),
            "delivery_instructions": forms.Textarea(attrs={"class": "lux-input", "rows": 3, "maxlength": 500}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.checkout_user = user
        super().__init__(*args, **kwargs)

    def clean_full_name(self):
        value = " ".join((self.cleaned_data.get("full_name") or "").split())
        if len(value) < 2:
            raise forms.ValidationError("Please enter your full name.")
        return value

    def clean_email(self):
        submitted = (self.cleaned_data.get("email") or "").strip().lower()

        if not self.checkout_user or not self.checkout_user.is_authenticated:
            raise forms.ValidationError("Please sign in before checkout.")

        account_email = (self.checkout_user.email or "").strip().lower()
        if not account_email:
            raise forms.ValidationError("Your account does not have an email address.")

        if submitted != account_email:
            raise forms.ValidationError("Checkout email must match your logged-in account email.")

        return account_email

    def clean_phone(self):
        value = (self.cleaned_data.get("phone") or "").strip()
        compact = re.sub(r"[\s-]", "", value)
        if not re.fullmatch(r"(?:\+91)?[6-9]\d{9}", compact):
            raise forms.ValidationError("Enter a valid Indian mobile number.")
        return compact

    def clean_address(self):
        value = " ".join((self.cleaned_data.get("address") or "").split())
        if len(value) < 5:
            raise forms.ValidationError("Please enter a complete delivery address.")
        return value

    def clean_city(self):
        value = " ".join((self.cleaned_data.get("city") or "").split())
        if len(value) < 2:
            raise forms.ValidationError("Please enter the city.")
        return value

    def clean_state(self):
        value = " ".join((self.cleaned_data.get("state") or "").split())
        if len(value) < 2:
            raise forms.ValidationError("Please enter the state.")
        return value

    def clean_pincode(self):
        value = re.sub(r"\D", "", self.cleaned_data.get("pincode") or "")
        if not re.fullmatch(r"[1-9]\d{5}", value):
            raise forms.ValidationError("Enter a valid 6-digit Indian pincode.")
        return value

    def clean_landmark(self):
        value = " ".join((self.cleaned_data.get("landmark") or "").split())
        if not value:
            raise forms.ValidationError("Please enter a nearby landmark.")
        return value

    def clean_country(self):
        value = " ".join((self.cleaned_data.get("country") or "India").split())
        if value.lower() != "india":
            raise forms.ValidationError("Delivery is currently available only in India.")
        return "India"


class PaymentProofForm(forms.ModelForm):
    class Meta:
        model = PaymentProof
        fields = ["payer_name", "paid_amount", "utr_number", "payment_date", "screenshot", "notes"]
        widgets = {
            "payer_name": forms.TextInput(attrs={"class": "form-control luxury-input", "placeholder": "Payer Name"}),
            "paid_amount": forms.NumberInput(attrs={"class": "form-control luxury-input", "placeholder": "Amount Paid"}),
            "utr_number": forms.TextInput(attrs={"class": "form-control luxury-input", "placeholder": "UTR / Transaction ID"}),
            "payment_date": forms.DateTimeInput(attrs={"class": "form-control luxury-input", "type": "datetime-local"}),
            "screenshot": forms.FileInput(attrs={"class": "form-control luxury-input"}),
            "notes": forms.Textarea(attrs={"class": "form-control luxury-input", "rows": 3, "placeholder": "Optional notes"}),
        }

    def clean_screenshot(self):
        upload = self.cleaned_data.get("screenshot")
        if not upload:
            return upload
        from django.conf import settings
        if upload.size > settings.MAX_PAYMENT_PROOF_SIZE:
            raise forms.ValidationError("Payment proof must be 5 MB or smaller.")
        content_type = getattr(upload, "content_type", "")
        if content_type and content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise forms.ValidationError("Upload a JPG, PNG or WEBP payment proof.")
        return upload

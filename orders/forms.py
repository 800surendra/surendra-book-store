from django import forms
from .models import Order, PaymentProof, Address

class DeliveryDetailsForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['full_name', 'email', 'phone', 'address', 'city', 'state', 'pincode', 'landmark']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control luxury-input', 'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control luxury-input', 'placeholder': 'Email'}),
            'phone': forms.TextInput(attrs={'class': 'form-control luxury-input', 'placeholder': 'Phone'}),
            'address': forms.Textarea(attrs={'class': 'form-control luxury-input', 'rows': 3, 'placeholder': 'Address'}),
            'city': forms.TextInput(attrs={'class': 'form-control luxury-input', 'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'class': 'form-control luxury-input', 'placeholder': 'State'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control luxury-input', 'placeholder': 'Pincode'}),
            'landmark': forms.TextInput(attrs={'class': 'form-control luxury-input', 'placeholder': 'Landmark (optional)'}),
        }

class PaymentProofForm(forms.ModelForm):
    class Meta:
        model = PaymentProof
        fields = ['payer_name', 'paid_amount', 'utr_number', 'payment_date', 'screenshot', 'notes']
        widgets = {
            'payer_name': forms.TextInput(attrs={'class': 'form-control luxury-input', 'placeholder': 'Payer Name'}),
            'paid_amount': forms.NumberInput(attrs={'class': 'form-control luxury-input', 'placeholder': 'Amount Paid'}),
            'utr_number': forms.TextInput(attrs={'class': 'form-control luxury-input', 'placeholder': 'UTR / Transaction ID'}),
            'payment_date': forms.DateTimeInput(attrs={'class': 'form-control luxury-input', 'type': 'datetime-local'}),
            'screenshot': forms.FileInput(attrs={'class': 'form-control luxury-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control luxury-input', 'rows': 3, 'placeholder': 'Optional notes'}),
        }
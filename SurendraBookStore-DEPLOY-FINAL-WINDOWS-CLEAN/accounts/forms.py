from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .validators import PasswordValidator

User = get_user_model()

# ===== PROFILE EDIT FORM =====
class ProfileEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={
        'class': 'luxury-input', 'placeholder': 'First Name'
    }))
    last_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={
        'class': 'luxury-input', 'placeholder': 'Last Name'
    }))
    username = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'class': 'luxury-input', 'placeholder': 'Username'
    }))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'luxury-input', 'placeholder': 'Email'
    }))
    phone = forms.CharField(max_length=17, required=False, widget=forms.TextInput(attrs={
        'class': 'luxury-input', 'placeholder': 'Phone'
    }))
    bio = forms.CharField(max_length=500, required=False, widget=forms.Textarea(attrs={
        'class': 'luxury-input', 'rows': 3, 'placeholder': 'Tell us about yourself'
    }))
    gender = forms.ChoiceField(choices=User._meta.get_field('gender').choices, required=False, widget=forms.Select(attrs={
        'class': 'luxury-input'
    }))
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={
        'class': 'luxury-input', 'type': 'date'
    }))
    address = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={
        'class': 'luxury-input', 'placeholder': 'Address'
    }))
    city = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={
        'class': 'luxury-input', 'placeholder': 'City'
    }))
    state = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={
        'class': 'luxury-input', 'placeholder': 'State'
    }))
    pincode = forms.CharField(max_length=10, required=False, widget=forms.TextInput(attrs={
        'class': 'luxury-input', 'placeholder': 'Pincode'
    }))
    country = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={
        'class': 'luxury-input', 'placeholder': 'Country'
    }))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'bio', 
                  'gender', 'date_of_birth', 'address', 'city', 'state', 'pincode', 'country']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.exclude(pk=self.instance.pk).filter(username=username).exists():
            raise ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        return email


# ===== REGISTRATION FORM =====
class LuxuryRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Enter your first name',
    }))
    last_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Enter your last name',
    }))
    username = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Choose a username',
    }))
    email = forms.EmailField(max_length=200, required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Enter your email address',
    }))
    phone = forms.CharField(max_length=17, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': '+91 98765 43210',
    }))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Create a password',
    }))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Confirm your password',
    }))
    
    country = forms.CharField(max_length=100, required=True, initial='India', widget=forms.TextInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Country',
    }))
    state = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'State',
    }))
    city = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'City',
    }))
    
    referral_code = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Referral Code (Optional)',
    }))
    
    terms = forms.BooleanField(required=True, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input me-2',
    }))
    newsletter = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input me-2',
    }))
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages = {'required': 'This field is required.'}
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        return email
    
    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError('This username is already taken.')
        return username
    
    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if User.objects.filter(phone=phone).exists():
            raise ValidationError('This phone number is already registered.')
        return phone
    
    def clean_password1(self):
        password = self.cleaned_data['password1']
        errors = PasswordValidator.validate_password_strength(password)
        if errors:
            raise ValidationError(errors)
        return password
    
    def clean_referral_code(self):
        code = self.cleaned_data.get('referral_code')
        if code:
            if not User.objects.filter(referral_code=code).exists():
                raise ValidationError('Invalid referral code.')
        return code


# ===== LOGIN FORM =====
class LuxuryLoginForm(AuthenticationForm):
    username = forms.EmailField(max_length=200, widget=forms.EmailInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Enter your email',
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control form-control-lg',
        'placeholder': 'Enter your password',
    }))
    remember_me = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input me-2',
    }))
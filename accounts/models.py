from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import RegexValidator
import random
import string
from datetime import timedelta

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

class User(AbstractUser):
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    email = models.EmailField(unique=True)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    
    # Profile fields
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    cover_photo = models.ImageField(upload_to='cover_photos/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    gender = models.CharField(max_length=10, choices=[
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('N', 'Prefer not to say')
    ], default='N')
    date_of_birth = models.DateField(null=True, blank=True)
    
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='India')
    pincode = models.CharField(max_length=10, blank=True)
    
    referral_code = models.CharField(max_length=20, blank=True, null=True)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    
    newsletter_subscribed = models.BooleanField(default=False)
    
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_device = models.CharField(max_length=255, blank=True)
    last_login_location = models.CharField(max_length=255, blank=True)
    login_attempts = models.IntegerField(default=0)
    is_locked = models.BooleanField(default=False)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_profile_completion(self):
        fields = ['first_name', 'last_name', 'phone', 'bio', 'address', 'city', 'state', 'pincode']
        filled = sum(1 for field in fields if getattr(self, field, ''))
        return int((filled / len(fields)) * 100)
    
    def lock_account(self, minutes=30):
        self.is_locked = True
        self.locked_until = timezone.now() + timedelta(minutes=minutes)
        self.save()
    
    def unlock_account(self):
        self.is_locked = False
        self.locked_until = None
        self.login_attempts = 0
        self.save()


class OTPVerification(models.Model):
    OTP_TYPES = (
        ('email_verify', 'Email Verification'),
        ('email_login', 'Email Login'),
        ('password_reset', 'Password Reset'),
        ('email_change', 'Email Change'),   # ✅ Added
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps', null=True, blank=True)
    email = models.EmailField()
    otp = models.CharField(max_length=6, default=generate_otp)
    otp_type = models.CharField(max_length=20, choices=OTP_TYPES)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        return not self.is_expired() and not self.is_used and self.attempts < self.max_attempts
    
    def increment_attempts(self):
        self.attempts += 1
        self.save()
        return self.attempts
    
    def mark_used(self):
        self.is_used = True
        self.save()
    
    def __str__(self):
        return f"OTP for {self.email} - {self.otp_type}"


class LoginLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_logs')
    ip_address = models.GenericIPAddressField()
    device = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    user_agent = models.TextField()
    status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('locked', 'Locked')
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.status} at {self.created_at}"
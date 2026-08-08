from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, OTPVerification, LoginLog

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_active', 'is_email_verified', 'get_profile_completion', 'created_at')
    list_filter = ('is_active', 'is_email_verified', 'is_staff', 'is_superuser')
    search_fields = ('email', 'username', 'first_name', 'last_name', 'phone')
    readonly_fields = ('last_login', 'created_at', 'updated_at', 'last_login_ip', 'last_login_device', 'login_attempts')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Profile Details', {'fields': ('phone', 'profile_photo', 'cover_photo', 'bio', 'gender', 'date_of_birth')}),
        ('Address', {'fields': ('address', 'city', 'state', 'country', 'pincode')}),
        ('Verification', {'fields': ('is_email_verified', 'is_phone_verified')}),
        ('Referral', {'fields': ('referral_code', 'referred_by')}),
        ('Security', {'fields': ('login_attempts', 'is_locked', 'locked_until')}),
        ('Preferences', {'fields': ('newsletter_subscribed',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'first_name', 'last_name'),
        }),
    )

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp', 'otp_type', 'attempts', 'is_used', 'is_expired', 'created_at')
    list_filter = ('otp_type', 'is_used')
    search_fields = ('email', 'otp')
    readonly_fields = ('created_at', 'expires_at')

@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'device', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__email', 'ip_address')
    readonly_fields = ('created_at',)
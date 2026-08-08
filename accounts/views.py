from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import timedelta
import json

from .forms import LuxuryRegistrationForm, LuxuryLoginForm, ProfileEditForm
from .models import OTPVerification, LoginLog, User
from .services import OTPService, LoginLogService
from .validators import PasswordValidator

User = get_user_model()

# ===== LANDING =====
def landing(request):
    return render(request, 'accounts/landing.html')

# ===== REGISTER =====
def register(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    
    if request.method == 'POST':
        form = LuxuryRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.is_email_verified = False
            user.save()
            
            otp_obj = OTPService.send_otp_email(user, user.email, 'email_verify')
            if otp_obj:
                request.session['otp_user_id'] = user.id
                request.session['otp_email'] = user.email
                request.session['otp_type'] = 'email_verify'
                messages.success(request, f'OTP sent to {user.email}. Please verify your email.')
                return redirect('accounts:verify_otp')
            else:
                messages.error(request, 'Failed to send OTP. Please try again.')
                user.delete()
                return render(request, 'accounts/register.html', {'form': form})
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = LuxuryRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})

# ===== LOGIN =====
def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    
    if request.method == 'POST':
        form = LuxuryLoginForm(request, data=request.POST)
        email = request.POST.get('username')
        password = request.POST.get('password')
        
        user = User.objects.filter(email=email).first()
        
        if user:
            if user.is_locked:
                if user.locked_until and user.locked_until > timezone.now():
                    messages.error(request, f'Account locked. Try after {user.locked_until.strftime("%I:%M %p")}')
                    return render(request, 'accounts/login.html', {'form': form})
                else:
                    user.unlock_account()
            
            if not user.is_active or not user.is_email_verified:
                otp_obj = OTPService.send_otp_email(user, user.email, 'email_verify')
                request.session['otp_user_id'] = user.id
                request.session['otp_email'] = user.email
                request.session['otp_type'] = 'email_verify'
                messages.warning(request, 'Please verify your email first. OTP resent.')
                return redirect('accounts:verify_otp')
            
            if user.check_password(password):
                otp_obj = OTPService.send_otp_email(user, user.email, 'email_login')
                if otp_obj:
                    request.session['login_user_id'] = user.id
                    request.session['otp_email'] = user.email
                    request.session['otp_type'] = 'email_login'
                    messages.success(request, f'OTP sent to {user.email}. Please verify to login.')
                    LoginLogService.log_login(user, request, 'success')
                    return redirect('accounts:verify_otp')
                else:
                    messages.error(request, 'Failed to send OTP. Please try again.')
            else:
                user.login_attempts += 1
                if user.login_attempts >= 5:
                    user.lock_account()
                    messages.error(request, 'Too many failed attempts. Account locked for 30 minutes.')
                else:
                    messages.error(request, 'Invalid password. Please try again.')
                user.save()
                LoginLogService.log_login(user, request, 'failed')
        else:
            messages.error(request, 'No account found with this email.')
    
    form = LuxuryLoginForm()
    return render(request, 'accounts/login.html', {'form': form})

# ===== FORGOT PASSWORD =====
def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if not email:
            messages.error(request, 'Please enter your email.')
            return render(request, 'accounts/forgot_password.html')
        
        user = User.objects.filter(email=email).first()
        if not user:
            messages.error(request, 'No account found with this email.')
            return render(request, 'accounts/forgot_password.html')
        
        otp_obj = OTPService.send_otp_email(user, email, 'password_reset')
        if otp_obj:
            request.session['otp_email'] = email
            request.session['otp_type'] = 'password_reset'
            request.session['otp_user_id'] = user.id
            messages.success(request, f'OTP sent to {email}. Please verify to reset password.')
            return redirect('accounts:verify_otp')
        else:
            messages.error(request, 'Failed to send OTP. Please try again.')
    
    return render(request, 'accounts/forgot_password.html')

# ===== VERIFY OTP =====
def verify_otp(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    
    if request.method == 'POST':
        otp_input = request.POST.get('otp')
        email = request.session.get('otp_email')
        otp_type = request.session.get('otp_type')
        
        if not email or not otp_type:
            messages.error(request, 'Session expired. Please try again.')
            return redirect('accounts:login')
        
        result = OTPService.verify_otp(email, otp_input, otp_type)
        
        if result['success']:
            if otp_type == 'email_verify':
                user_id = request.session.get('otp_user_id')
                user = User.objects.filter(id=user_id).first()
                if user:
                    user.is_active = True
                    user.is_email_verified = True
                    user.save()
                    messages.success(request, 'Email verified successfully! Please login.')
                    try:
                        subject = 'Welcome to Surendra BookStore! 🎉'
                        html_message = render_to_string('emails/welcome_email.html', {'user': user})
                        send_mail(subject, '', settings.DEFAULT_FROM_EMAIL, [user.email], html_message=html_message)
                    except:
                        pass
                    return redirect('accounts:login')
            
            elif otp_type == 'email_login':
                user_id = request.session.get('login_user_id')
                user = User.objects.filter(id=user_id).first()
                if user:
                    login(request, user)
                    if request.POST.get('remember_me'):
                        request.session.set_expiry(60 * 60 * 24 * 30)
                    request.session.pop('login_user_id', None)
                    request.session.pop('otp_email', None)
                    request.session.pop('otp_type', None)
                    messages.success(request, f'Welcome back, {user.get_full_name()}!')
                    return redirect('core:home')
            
            elif otp_type == 'password_reset':
                request.session['reset_email'] = email
                return redirect('accounts:reset_password')
        
        else:
            messages.error(request, result['message'])
        
        return render(request, 'accounts/verify_otp.html')
    
    return render(request, 'accounts/verify_otp.html')

# ===== RESEND OTP =====
def resend_otp(request):
    email = request.session.get('otp_email')
    otp_type = request.session.get('otp_type')
    user_id = request.session.get('otp_user_id') or request.session.get('login_user_id')
    
    if not email or not otp_type:
        messages.error(request, 'Session expired. Please try again.')
        return redirect('accounts:login')
    
    user = User.objects.filter(id=user_id).first() if user_id else None
    if not user:
        user = User.objects.filter(email=email).first()
    
    if user:
        otp_obj = OTPService.send_otp_email(user, email, otp_type)
        if otp_obj:
            request.session['otp_email'] = email
            request.session['otp_type'] = otp_type
            if user_id:
                request.session['otp_user_id'] = user_id
            messages.success(request, f'New OTP sent to {email}.')
        else:
            messages.error(request, 'Failed to send OTP. Please try again.')
    else:
        messages.error(request, 'User not found. Please try again.')
    
    return redirect('accounts:verify_otp')

# ===== RESET PASSWORD =====
def reset_password(request):
    email = request.session.get('reset_email')
    if not email:
        messages.error(request, 'Session expired. Please try again.')
        return redirect('accounts:forgot_password')
    
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'accounts/reset_password.html')
        
        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return render(request, 'accounts/reset_password.html')
        
        user = User.objects.filter(email=email).first()
        if user:
            user.set_password(password)
            user.save()
            request.session.pop('reset_email', None)
            messages.success(request, 'Password reset successfully! Please login.')
            return redirect('accounts:login')
        else:
            messages.error(request, 'User not found.')
            return redirect('accounts:forgot_password')
    
    return render(request, 'accounts/reset_password.html')

# ===== PROFILE =====
@login_required
def my_profile(request):
    user = request.user
    profile_completion = user.get_profile_completion() if hasattr(user, 'get_profile_completion') else 0
    
    # Circle calculation
    circumference = 314.16  # 2 * pi * 50
    dash_offset = circumference * (1 - profile_completion / 100)
    
    from orders.models import Order
    from cart.models import Cart
    orders_count = Order.objects.filter(user=user).count()
    cart = Cart.objects.filter(user=user).first()
    cart_items_count = cart.get_total_items() if cart else 0
    
    return render(request, 'accounts/profile.html', {
        'user': user,
        'profile_completion': profile_completion,
        'dash_offset': dash_offset,
        'orders_count': orders_count,
        'cart_items_count': cart_items_count,
    })

# ===== EDIT PROFILE =====
@login_required
def edit_profile(request):
    user = request.user
    
    # Handle photo uploads from profile page (AJAX-like)
    if request.method == 'POST':
        # Check if this is a photo-only upload (from profile page)
        if 'upload_profile' in request.POST or 'upload_cover' in request.POST:
            # Only update photo fields
            if 'profile_photo' in request.FILES:
                user.profile_photo = request.FILES['profile_photo']
            if 'cover_photo' in request.FILES:
                user.cover_photo = request.FILES['cover_photo']
            user.save()
            messages.success(request, 'Photo updated successfully!')
            return redirect('accounts:my_profile')
        
        # Full profile edit (from edit_profile page)
        form = ProfileEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:my_profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ProfileEditForm(instance=user)
    
    return render(request, 'accounts/edit_profile.html', {'form': form, 'user': user})

# ===== CHANGE PASSWORD =====
@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
            return redirect('accounts:my_profile')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})

# ===== CHANGE EMAIL WITH OTP =====
@login_required
def change_email(request):
    if request.method == 'POST':
        new_email = request.POST.get('new_email')
        if new_email:
            if User.objects.exclude(pk=request.user.pk).filter(email=new_email).exists():
                messages.error(request, 'This email is already registered.')
                return render(request, 'accounts/change_email.html')
            
            # Send OTP to new email
            otp_obj = OTPService.send_otp_email(request.user, new_email, 'email_change')
            if otp_obj:
                request.session['new_email'] = new_email
                request.session['otp_email'] = new_email
                request.session['otp_type'] = 'email_change'
                request.session['otp_user_id'] = request.user.id
                messages.success(request, f'OTP sent to {new_email}. Please verify.')
                return redirect('accounts:verify_otp')
            else:
                messages.error(request, 'Failed to send OTP. Please try again.')
        else:
            messages.error(request, 'Please enter a valid email.')
    
    return render(request, 'accounts/change_email.html')

# ===== LOGOUT =====
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('core:home')
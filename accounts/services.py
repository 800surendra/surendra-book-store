from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random
import string
from .models import OTPVerification, LoginLog

class OTPService:
    @staticmethod
    def generate_otp():
        return ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def send_otp_email(user, email, otp_type):
        otp = OTPService.generate_otp()
        
        # Create OTP record
        otp_obj = OTPVerification.objects.create(
            user=user,
            email=email,
            otp=otp,
            otp_type=otp_type,
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        # Send Email
        try:
            subject = f"Your {dict(OTPVerification.OTP_TYPES)[otp_type]} - Surendra BookStore"
            html_message = render_to_string('emails/otp_email.html', {
                'user': user,
                'otp': otp,
                'otp_type': dict(OTPVerification.OTP_TYPES)[otp_type],
                'expiry_minutes': 5
            })
            plain_message = f"Your OTP is: {otp}. It expires in 5 minutes."
            
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            return otp_obj
        except Exception as e:
            print(f"Error sending email: {e}")
            return None
    
    @staticmethod
    def verify_otp(email, otp, otp_type):
        try:
            otp_obj = OTPVerification.objects.filter(
                email=email,
                otp=otp,
                otp_type=otp_type,
                is_used=False
            ).latest('created_at')
            
            if otp_obj.is_expired():
                return {'success': False, 'message': 'OTP has expired. Please request a new one.'}
            
            if otp_obj.attempts >= otp_obj.max_attempts:
                return {'success': False, 'message': 'Maximum attempts exceeded. Please request a new OTP.'}
            
            otp_obj.mark_used()
            return {'success': True, 'message': 'OTP verified successfully.'}
            
        except OTPVerification.DoesNotExist:
            return {'success': False, 'message': 'Invalid OTP. Please try again.'}

class LoginLogService:
    @staticmethod
    def log_login(user, request, status='success'):
        try:
            ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or request.META.get('REMOTE_ADDR', '')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            LoginLog.objects.create(
                user=user,
                ip_address=ip,
                device=LoginLogService.get_device_info(user_agent),
                location='Unknown',  # You can integrate IP geolocation API here
                user_agent=user_agent,
                status=status
            )
        except Exception as e:
            print(f"Error logging login: {e}")
    
    @staticmethod
    def get_device_info(user_agent):
        # Simple device detection - you can expand this
        if 'Mobile' in user_agent:
            return 'Mobile'
        elif 'Tablet' in user_agent:
            return 'Tablet'
        else:
            return 'Desktop'
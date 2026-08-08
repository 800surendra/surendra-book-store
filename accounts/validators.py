from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import re

class PasswordValidator:
    @staticmethod
    def validate_password_strength(password):
        errors = []
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter.")
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one digit.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character.")
        return errors
    
    @staticmethod
    def validate_phone_number(phone):
        phone_regex = re.compile(r'^\+?1?\d{9,15}$')
        if not phone_regex.match(phone):
            raise ValidationError("Phone number must be valid with country code.")
        return phone
    
    @staticmethod
    def validate_email_domain(email):
        allowed_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']  # Add more if needed
        domain = email.split('@')[1] if '@' in email else ''
        # Allow all domains, but you can restrict if needed
        return True

def validate_password(password):
    return PasswordValidator.validate_password_strength(password)
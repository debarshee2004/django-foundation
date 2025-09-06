"""
Authentication utility functions
Provides helper functions for security, validation, and user management
"""

from django.http import HttpRequest
from django.conf import settings
from urllib.parse import urlparse
import logging
import re

logger = logging.getLogger('auth')


def get_client_ip(request: HttpRequest) -> str:
    """
    Extract the real client IP address from the request
    
    Handles cases where the app is behind a proxy/load balancer
    and checks various headers to find the actual client IP
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        str: Client IP address
    """
    # List of headers to check for real IP (in order of preference)
    ip_headers = [
        'HTTP_X_FORWARDED_FOR',      # Most common proxy header
        'HTTP_X_REAL_IP',            # Nginx proxy header
        'HTTP_X_FORWARDED',          # Alternative proxy header
        'HTTP_X_CLUSTER_CLIENT_IP',  # Cluster/load balancer header
        'HTTP_FORWARDED_FOR',        # Standard forwarded header
        'HTTP_FORWARDED',            # RFC 7239 standard
        'REMOTE_ADDR',               # Direct connection (fallback)
    ]
    
    for header in ip_headers:
        ip = request.META.get(header)
        if ip:
            # Handle comma-separated IPs (X-Forwarded-For can have multiple IPs)
            # The first IP is usually the real client IP
            ip = ip.split(',')[0].strip()
            
            # Basic IP validation
            if _is_valid_ip(ip):
                return ip
    
    # Fallback to REMOTE_ADDR if nothing else works
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def get_user_agent(request: HttpRequest) -> str:
    """
    Extract user agent string from request
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        str: User agent string (truncated to reasonable length)
    """
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    
    # Truncate very long user agent strings to prevent database issues
    max_length = 500
    if len(user_agent) > max_length:
        user_agent = user_agent[:max_length] + '...'
    
    return user_agent


def is_safe_url(url: str, allowed_hosts: str = None) -> bool:
    """
    Check if a URL is safe for redirecting
    
    Prevents open redirect vulnerabilities by ensuring the URL
    either has no host (relative URL) or belongs to allowed hosts
    
    Args:
        url: URL to check
        allowed_hosts: Allowed host (defaults to current host)
        
    Returns:
        bool: True if URL is safe for redirect
    """
    if not url:
        return False
    
    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    
    # Allow relative URLs (no host specified)
    if not parsed.netloc:
        return True
    
    # Check if the host is in allowed hosts
    if allowed_hosts:
        allowed_hosts_list = [allowed_hosts] if isinstance(allowed_hosts, str) else allowed_hosts
        return parsed.netloc in allowed_hosts_list
    
    return False


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Validate password strength according to security requirements
    
    Args:
        password: Password to validate
        
    Returns:
        tuple: (is_valid, list_of_error_messages)
    """
    errors = []
    
    # Minimum length check
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    # Maximum length check (to prevent DoS attacks)
    if len(password) > 128:
        errors.append("Password must be less than 128 characters")
    
    # Character variety checks
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one number")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character")
    
    # Common password checks
    common_passwords = [
        'password', '123456', '123456789', 'qwerty', 'abc123',
        'password123', 'admin', 'letmein', 'welcome', '12345678'
    ]
    
    if password.lower() in common_passwords:
        errors.append("Password is too common, please choose a different one")
    
    # Sequential characters check
    if _has_sequential_chars(password):
        errors.append("Password should not contain sequential characters")
    
    return len(errors) == 0, errors


def generate_username_suggestions(base_username: str, email: str = None) -> list[str]:
    """
    Generate username suggestions based on a base username or email
    
    Args:
        base_username: Base username to generate suggestions from
        email: Optional email to extract username from
        
    Returns:
        list: List of username suggestions
    """
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    suggestions = []
    
    # Start with the base username
    if base_username:
        base = re.sub(r'[^a-zA-Z0-9_]', '', base_username.lower())
    elif email:
        # Extract username part from email
        base = re.sub(r'[^a-zA-Z0-9_]', '', email.split('@')[0].lower())
    else:
        return suggestions
    
    # Ensure minimum length
    if len(base) < 3:
        base = base + '123'
    
    # Generate variations
    variations = [
        base,
        base + '123',
        base + '2024',
        base + '_user',
        'user_' + base,
        base + str(hash(base) % 1000),  # Add a hash-based number
    ]
    
    # Check availability and add to suggestions
    for variation in variations:
        if len(variation) >= 3 and not User.objects.filter(username__iexact=variation).exists():
            suggestions.append(variation)
            if len(suggestions) >= 5:  # Limit suggestions
                break
    
    return suggestions


def sanitize_user_input(input_string: str, max_length: int = 255) -> str:
    """
    Sanitize user input to prevent XSS and other attacks
    
    Args:
        input_string: Input string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        str: Sanitized string
    """
    if not input_string:
        return ""
    
    # Strip whitespace
    sanitized = input_string.strip()
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Remove potentially dangerous characters
    # Allow letters, numbers, spaces, and common punctuation
    sanitized = re.sub(r'[<>"\']', '', sanitized)
    
    return sanitized


def format_user_display_name(user) -> str:
    """
    Format a user's display name consistently across the application
    
    Args:
        user: User model instance
        
    Returns:
        str: Formatted display name
    """
    if hasattr(user, 'get_full_name') and user.get_full_name():
        return user.get_full_name()
    elif hasattr(user, 'get_short_name') and user.get_short_name():
        return user.get_short_name()
    elif user.username:
        return user.username
    elif user.email:
        return user.email.split('@')[0]
    else:
        return "User"


def check_password_reuse(user, new_password: str, check_last_n: int = 5) -> bool:
    """
    Check if the new password was recently used by the user
    
    Note: This is a placeholder function. In a real implementation,
    you would store password hashes in a separate model to check against.
    
    Args:
        user: User model instance
        new_password: New password to check
        check_last_n: Number of previous passwords to check against
        
    Returns:
        bool: True if password was recently used
    """
    # This is a simplified implementation
    # In production, you'd want to store and check against previous password hashes
    
    # For now, just check against current password
    if hasattr(user, 'check_password'):
        return user.check_password(new_password)
    
    return False


# ============================================================================
# PRIVATE HELPER FUNCTIONS
# ============================================================================

def _is_valid_ip(ip: str) -> bool:
    """
    Basic IP address validation
    
    Args:
        ip: IP address string to validate
        
    Returns:
        bool: True if IP appears valid
    """
    # Basic IPv4 validation
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    
    try:
        for part in parts:
            num = int(part)
            if not 0 <= num <= 255:
                return False
        return True
    except ValueError:
        return False


def _has_sequential_chars(password: str, min_sequence: int = 3) -> bool:
    """
    Check if password contains sequential characters
    
    Args:
        password: Password to check
        min_sequence: Minimum sequence length to flag
        
    Returns:
        bool: True if sequential characters found
    """
    # Check for sequential numbers (123, 321, etc.)
    for i in range(len(password) - min_sequence + 1):
        substring = password[i:i + min_sequence]
        
        # Check ascending sequence
        if all(ord(substring[j]) == ord(substring[0]) + j for j in range(len(substring))):
            return True
        
        # Check descending sequence
        if all(ord(substring[j]) == ord(substring[0]) - j for j in range(len(substring))):
            return True
    
    return False


def log_security_event(event_type: str, user=None, ip_address: str = None, details: dict = None):
    """
    Log security-related events for monitoring and analysis
    
    Args:
        event_type: Type of security event (login_fail, password_change, etc.)
        user: User associated with the event (if any)
        ip_address: IP address where event occurred
        details: Additional details about the event
    """
    try:
        log_message = f"Security Event: {event_type}"
        
        if user:
            log_message += f" | User: {user.email}"
        
        if ip_address:
            log_message += f" | IP: {ip_address}"
        
        if details:
            log_message += f" | Details: {details}"
        
        logger.warning(log_message)
        
    except Exception as e:
        # Don't let logging errors break the application
        logger.error(f"Failed to log security event: {str(e)}")

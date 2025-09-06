from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import EmailValidator
from django.utils import timezone
import uuid

# Create your models here.

class CustomUser(AbstractUser):
    """
    Custom User model extending Django's AbstractUser
    Adds additional fields for SaaS functionality and better email handling
    """
    # Override email field to make it unique and required
    email = models.EmailField(
        unique=True, 
        validators=[EmailValidator()],
        help_text="Required. Enter a valid email address."
    )
    
    # Additional user profile fields
    first_name = models.CharField(
        max_length=150, 
        blank=True, 
        help_text="User's first name"
    )
    last_name = models.CharField(
        max_length=150, 
        blank=True, 
        help_text="User's last name"
    )
    
    # Email verification status
    email_verified = models.BooleanField(
        default=False,
        help_text="Whether the user's email has been verified"
    )
    
    # User preferences
    receive_marketing_emails = models.BooleanField(
        default=True,
        help_text="Whether user wants to receive marketing emails"
    )
    
    # Account status tracking
    last_login_ip = models.GenericIPAddressField(
        null=True, 
        blank=True,
        help_text="IP address of user's last login"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the account was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the account was last updated"
    )
    
    # Use email as the username field for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # Required when creating superuser
    
    class Meta:
        app_label = 'auth'
        db_table = 'auth_custom_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['email_verified']),
        ]
    
    def __str__(self):
        """String representation of the user"""
        return f"{self.email} ({self.username})"
    
    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.username
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.username
    
    @property
    def display_name(self):
        """Property to get the best display name for the user"""
        return self.get_full_name()


class UserProfile(models.Model):
    """
    Extended user profile for additional SaaS-specific information
    This is separate from the User model to keep auth-related fields separate
    """
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='profile',
        help_text="Associated user account"
    )
    
    # Profile information
    bio = models.TextField(
        max_length=500, 
        blank=True,
        help_text="User's biography or description"
    )
    
    # Contact information
    phone_number = models.CharField(
        max_length=20, 
        blank=True,
        help_text="User's phone number"
    )
    
    # Location information
    country = models.CharField(
        max_length=100, 
        blank=True,
        help_text="User's country"
    )
    user_timezone = models.CharField(
        max_length=50, 
        default='UTC',
        help_text="User's preferred timezone"
    )
    
    # Profile image
    avatar = models.URLField(
        blank=True,
        help_text="URL to user's avatar image"
    )
    
    # Account settings
    language_preference = models.CharField(
        max_length=10, 
        default='en',
        choices=[
            ('en', 'English'),
            ('es', 'Spanish'),
            ('fr', 'French'),
            ('de', 'German'),
            ('hi', 'Hindi'),
        ],
        help_text="User's preferred language"
    )
    
    # Notifications preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text="Whether to send email notifications"
    )
    push_notifications = models.BooleanField(
        default=True,
        help_text="Whether to send push notifications"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the profile was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the profile was last updated"
    )
    
    class Meta:
        db_table = 'auth_user_profile'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile for {self.user.email}"


class SocialAccount(models.Model):
    """
    Track social media accounts linked to user accounts
    This provides additional tracking beyond what allauth provides
    """
    PROVIDER_CHOICES = [
        ('google', 'Google'),
        ('github', 'GitHub'),
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter'),
        ('linkedin', 'LinkedIn'),
    ]
    
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='social_accounts',
        help_text="User who owns this social account"
    )
    
    provider = models.CharField(
        max_length=20, 
        choices=PROVIDER_CHOICES,
        help_text="Social media provider"
    )
    
    provider_id = models.CharField(
        max_length=100,
        help_text="User ID from the social provider"
    )
    
    provider_email = models.EmailField(
        blank=True,
        help_text="Email from the social provider"
    )
    
    provider_name = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Display name from the social provider"
    )
    
    avatar_url = models.URLField(
        blank=True,
        help_text="Avatar URL from the social provider"
    )
    
    # Account status
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether this social account is verified by the provider"
    )
    
    # Additional data from provider (stored as JSON)
    extra_data = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Additional data from the social provider"
    )
    
    # Timestamps
    connected_at = models.DateTimeField(
        default=timezone.now,
        help_text="When this social account was first connected"
    )
    last_used = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When this social account was last used for login"
    )
    
    class Meta:
        db_table = 'auth_social_account'
        verbose_name = 'Social Account'
        verbose_name_plural = 'Social Accounts'
        unique_together = ['provider', 'provider_id']
        indexes = [
            models.Index(fields=['user', 'provider']),
            models.Index(fields=['provider', 'provider_id']),
        ]
    
    def __str__(self):
        return f"{self.provider} account for {self.user.email}"


class LoginAttempt(models.Model):
    """
    Track login attempts for security monitoring
    Helps identify brute force attacks and suspicious activity
    """
    # User information (can be null for failed attempts)
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        help_text="User who attempted to login (null for failed attempts)"
    )
    
    # Attempt details
    email_attempted = models.EmailField(
        help_text="Email address used in login attempt"
    )
    
    success = models.BooleanField(
        default=False,
        help_text="Whether the login attempt was successful"
    )
    
    failure_reason = models.CharField(
        max_length=100, 
        blank=True,
        choices=[
            ('invalid_credentials', 'Invalid Credentials'),
            ('account_disabled', 'Account Disabled'),
            ('email_not_verified', 'Email Not Verified'),
            ('too_many_attempts', 'Too Many Attempts'),
            ('suspicious_activity', 'Suspicious Activity'),
        ],
        help_text="Reason for login failure"
    )
    
    # Security information
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the login attempt"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string from the browser"
    )
    
    # Geolocation (optional)
    country = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Country of the IP address"
    )
    
    city = models.CharField(
        max_length=100, 
        blank=True,
        help_text="City of the IP address"
    )
    
    # Timestamp
    attempted_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the login attempt occurred"
    )
    
    class Meta:
        db_table = 'auth_login_attempt'
        verbose_name = 'Login Attempt'
        verbose_name_plural = 'Login Attempts'
        indexes = [
            models.Index(fields=['email_attempted']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['attempted_at']),
            models.Index(fields=['success']),
        ]
        ordering = ['-attempted_at']
    
    def __str__(self):
        status = "SUCCESS" if self.success else "FAILED"
        return f"{status}: {self.email_attempted} from {self.ip_address}"

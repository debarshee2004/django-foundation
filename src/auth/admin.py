from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import CustomUser, UserProfile, SocialAccount, LoginAttempt

User = get_user_model()

# ============================================================================
# CUSTOM USER ADMIN
# ============================================================================

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """
    Custom admin interface for the CustomUser model
    
    Extends Django's default UserAdmin to include our custom fields
    and provides better organization of user information
    """
    
    # Fields to display in the user list view
    list_display = [
        'email', 
        'username', 
        'get_full_name', 
        'is_staff', 
        'is_active',
        'email_verified',
        'date_joined',
        'last_login',
        'get_login_count'
    ]
    
    # Fields that can be used to filter the user list
    list_filter = [
        'is_staff', 
        'is_superuser', 
        'is_active',
        'email_verified',
        'receive_marketing_emails',
        'date_joined',
        'last_login'
    ]
    
    # Fields that can be searched
    search_fields = ['email', 'username', 'first_name', 'last_name']
    
    # Default ordering (most recent first)
    ordering = ['-date_joined']
    
    # Fields that are read-only
    readonly_fields = [
        'date_joined', 
        'last_login', 
        'last_login_ip',
        'created_at',
        'updated_at',
        'get_login_count',
        'get_social_accounts'
    ]
    
    # Organize fields into sections for better UX
    fieldsets = (
        # Basic Information
        ('User Information', {
            'fields': ('username', 'email', 'password')
        }),
        
        # Personal Information
        ('Personal Details', {
            'fields': ('first_name', 'last_name'),
            'classes': ('collapse',)  # Make this section collapsible
        }),
        
        # Permissions and Status
        ('Permissions & Status', {
            'fields': (
                'is_active', 
                'is_staff', 
                'is_superuser',
                'email_verified',
                'groups', 
                'user_permissions'
            ),
        }),
        
        # Preferences
        ('User Preferences', {
            'fields': ('receive_marketing_emails',),
            'classes': ('collapse',)
        }),
        
        # Security Information
        ('Security Information', {
            'fields': (
                'last_login', 
                'last_login_ip',
                'get_login_count',
                'get_social_accounts'
            ),
            'classes': ('collapse',)
        }),
        
        # Timestamps
        ('Timestamps', {
            'fields': ('date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Fields for creating new users
    add_fieldsets = (
        ('Required Information', {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
        ('Optional Information', {
            'classes': ('wide', 'collapse'),
            'fields': ('first_name', 'last_name'),
        }),
    )
    
    # Custom methods for the admin display
    
    def get_login_count(self, obj):
        """Display the number of successful logins for this user"""
        count = LoginAttempt.objects.filter(user=obj, success=True).count()
        return f"{count} logins"
    get_login_count.short_description = "Login Count"
    
    def get_social_accounts(self, obj):
        """Display linked social accounts"""
        social_accounts = SocialAccount.objects.filter(user=obj)
        if not social_accounts:
            return "None"
        
        accounts = []
        for account in social_accounts:
            accounts.append(f"{account.provider.title()}")
        
        return ", ".join(accounts)
    get_social_accounts.short_description = "Social Accounts"
    
    # Add custom actions
    actions = ['verify_email', 'unverify_email', 'send_welcome_email']
    
    def verify_email(self, request, queryset):
        """Mark selected users' emails as verified"""
        updated = queryset.update(email_verified=True)
        self.message_user(request, f"Verified email for {updated} users.")
    verify_email.short_description = "Mark emails as verified"
    
    def unverify_email(self, request, queryset):
        """Mark selected users' emails as unverified"""
        updated = queryset.update(email_verified=False)
        self.message_user(request, f"Unverified email for {updated} users.")
    unverify_email.short_description = "Mark emails as unverified"
    
    def send_welcome_email(self, request, queryset):
        """Send welcome email to selected users"""
        # This would integrate with your email service
        count = queryset.count()
        self.message_user(request, f"Welcome emails queued for {count} users.")
    send_welcome_email.short_description = "Send welcome email"


# ============================================================================
# USER PROFILE ADMIN
# ============================================================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for UserProfile model
    
    Manages extended user profile information
    """
    
    list_display = [
        'user_email',
        'get_full_name', 
        'country',
        'timezone',
        'language_preference',
        'email_notifications',
        'created_at'
    ]
    
    list_filter = [
        'country',
        'timezone', 
        'language_preference',
        'email_notifications',
        'push_notifications',
        'created_at'
    ]
    
    search_fields = [
        'user__email', 
        'user__username',
        'user__first_name', 
        'user__last_name',
        'country'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Profile Details', {
            'fields': ('bio', 'phone_number', 'avatar')
        }),
        ('Location & Preferences', {
            'fields': ('country', 'timezone', 'language_preference')
        }),
        ('Notification Settings', {
            'fields': ('email_notifications', 'push_notifications')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Custom display methods
    
    def user_email(self, obj):
        """Display the user's email"""
        return obj.user.email
    user_email.short_description = "Email"
    user_email.admin_order_field = 'user__email'
    
    def get_full_name(self, obj):
        """Display the user's full name"""
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = 'user__first_name'


# ============================================================================
# SOCIAL ACCOUNT ADMIN
# ============================================================================

@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    """
    Admin interface for SocialAccount model
    
    Manages social media account connections
    """
    
    list_display = [
        'user_email',
        'provider',
        'provider_name',
        'is_verified',
        'connected_at',
        'last_used'
    ]
    
    list_filter = [
        'provider',
        'is_verified',
        'connected_at',
        'last_used'
    ]
    
    search_fields = [
        'user__email',
        'user__username',
        'provider_email',
        'provider_name',
        'provider_id'
    ]
    
    readonly_fields = ['connected_at', 'provider_id', 'extra_data']
    
    fieldsets = (
        ('Account Information', {
            'fields': ('user', 'provider', 'provider_id')
        }),
        ('Provider Details', {
            'fields': ('provider_email', 'provider_name', 'avatar_url', 'is_verified')
        }),
        ('Usage Information', {
            'fields': ('connected_at', 'last_used')
        }),
        ('Additional Data', {
            'fields': ('extra_data',),
            'classes': ('collapse',)
        }),
    )
    
    # Custom display methods
    
    def user_email(self, obj):
        """Display the user's email"""
        return obj.user.email
    user_email.short_description = "User Email"
    user_email.admin_order_field = 'user__email'


# ============================================================================
# LOGIN ATTEMPT ADMIN
# ============================================================================

@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """
    Admin interface for LoginAttempt model
    
    Provides security monitoring and analysis of login attempts
    """
    
    list_display = [
        'attempted_at',
        'email_attempted',
        'success',
        'failure_reason',
        'ip_address',
        'country',
        'get_user_status'
    ]
    
    list_filter = [
        'success',
        'failure_reason',
        'attempted_at',
        'country'
    ]
    
    search_fields = [
        'email_attempted',
        'ip_address',
        'user__email',
        'country',
        'city'
    ]
    
    readonly_fields = [
        'attempted_at', 
        'user', 
        'email_attempted',
        'success',
        'failure_reason',
        'ip_address',
        'user_agent',
        'country',
        'city'
    ]
    
    # Make all fields read-only since this is a log
    def has_add_permission(self, request):
        """Disable adding login attempts through admin"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing login attempts through admin"""
        return False
    
    # Custom display methods
    
    def get_user_status(self, obj):
        """Display whether the user account exists and is active"""
        if obj.user:
            if obj.user.is_active:
                return format_html('<span style="color: green;">Active User</span>')
            else:
                return format_html('<span style="color: orange;">Inactive User</span>')
        else:
            return format_html('<span style="color: red;">No Account</span>')
    get_user_status.short_description = "User Status"
    
    # Custom admin actions
    actions = ['export_security_report']
    
    def export_security_report(self, request, queryset):
        """Export security report for selected login attempts"""
        # This would generate a security report
        count = queryset.count()
        self.message_user(request, f"Security report generated for {count} login attempts.")
    export_security_report.short_description = "Export security report"
    
    # Override queryset to show recent attempts by default
    def get_queryset(self, request):
        """Show only recent login attempts by default"""
        qs = super().get_queryset(request)
        
        # Show only last 30 days by default
        last_30_days = timezone.now() - timedelta(days=30)
        return qs.filter(attempted_at__gte=last_30_days)


# ============================================================================
# ADMIN SITE CUSTOMIZATION
# ============================================================================

# Customize the admin site header and title
admin.site.site_header = "SaaS Auth Administration"
admin.site.site_title = "SaaS Auth Admin"
admin.site.index_title = "Welcome to SaaS Auth Administration"

# Unregister the default User admin if we're using a custom user model
# This prevents conflicts with our CustomUserAdmin
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

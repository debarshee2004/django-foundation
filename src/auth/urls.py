"""
URL patterns for the authentication app

Defines all URL routes for authentication-related views including:
- Login/logout functionality
- User registration
- Profile management
- Password changes
- AJAX endpoints for form validation
- Social authentication (Google, GitHub)
"""

from django.urls import path, include
from . import views

# Set the app namespace for URL reversing
app_name = 'auth'

urlpatterns = [
    # ========================================================================
    # MAIN AUTHENTICATION VIEWS
    # ========================================================================
    
    # User login page
    # GET: Display login form
    # POST: Process login attempt
    path('login/', views.login_view, name='login'),
    
    # User registration page
    # GET: Display registration form
    # POST: Process registration
    path('register/', views.register_view, name='register'),
    
    # User logout (POST only for security)
    # POST: Log out current user
    path('logout/', views.logout_view, name='logout'),
    
    # ========================================================================
    # PROFILE MANAGEMENT
    # ========================================================================
    
    # User profile view and edit
    # GET: Display profile information
    # POST: Update profile information
    path('profile/', views.profile_view, name='profile'),
    
    # Change password functionality
    # POST: Change user's password
    path('profile/change-password/', views.change_password_view, name='change_password'),
    
    # ========================================================================
    # AJAX API ENDPOINTS
    # ========================================================================
    
    # Check email availability during registration
    # POST: Returns JSON with availability status
    path('api/check-email/', views.check_email_availability, name='check_email'),
    
    # Check username availability during registration
    # POST: Returns JSON with availability status
    path('api/check-username/', views.check_username_availability, name='check_username'),
    
    # ========================================================================
    # DJANGO-ALLAUTH INTEGRATION
    # ========================================================================
    
    # Include all django-allauth URLs for social authentication
    # This provides endpoints for:
    # - /accounts/google/login/ (Google OAuth)
    # - /accounts/github/login/ (GitHub OAuth)
    # - /accounts/signup/ (Social account signup)
    # - /accounts/email/ (Email management)
    # - /accounts/password/ (Password reset)
    # - And many more allauth endpoints
    path('accounts/', include('allauth.urls')),
]

# ============================================================================
# URL PATTERNS EXPLANATION
# ============================================================================

"""
The URL structure is organized as follows:

BASIC AUTHENTICATION:
- /auth/login/           - Login page
- /auth/register/        - Registration page  
- /auth/logout/          - Logout endpoint

PROFILE MANAGEMENT:
- /auth/profile/                    - View/edit profile
- /auth/profile/change-password/    - Change password

API ENDPOINTS:
- /auth/api/check-email/     - AJAX email availability check
- /auth/api/check-username/  - AJAX username availability check

SOCIAL AUTHENTICATION (via django-allauth):
- /auth/accounts/login/              - Allauth login page
- /auth/accounts/signup/             - Allauth signup page
- /auth/accounts/google/login/       - Google OAuth login
- /auth/accounts/github/login/       - GitHub OAuth login
- /auth/accounts/password/reset/     - Password reset
- /auth/accounts/email/              - Email management
- /auth/accounts/social/connections/ - Manage social connections

EMAIL VERIFICATION (via django-allauth):
- /auth/accounts/confirm-email/      - Email confirmation
- /auth/accounts/email/verify/       - Send verification email

PASSWORD RESET (via django-allauth):
- /auth/accounts/password/reset/     - Request password reset
- /auth/accounts/password/reset/done/ - Password reset sent
- /auth/accounts/password/reset/key/  - Password reset form

These URLs integrate with django-allauth to provide a complete
authentication system with social login capabilities.
"""

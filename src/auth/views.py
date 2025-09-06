from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.conf import settings
import logging
from datetime import timedelta

from .models import CustomUser, UserProfile, LoginAttempt
from .utils import get_client_ip, get_user_agent, is_safe_url

# Initialize logger for authentication events
logger = logging.getLogger("auth")

User = get_user_model()


@csrf_protect
@never_cache  # Prevent caching of login page
@require_http_methods(["GET", "POST"])  # Only allow GET and POST methods
def login_view(request):
    """
    Handle user login with email/password authentication

    Features:
    - Email-based authentication
    - Login attempt tracking for security
    - Rate limiting protection
    - Redirect to intended page after login

    GET: Display login form
    POST: Process login attempt
    """
    # Redirect authenticated users away from login page
    if request.user.is_authenticated:
        return redirect("home")

    # Get the page user was trying to access
    next_url = request.GET.get("next", "/")

    if request.method == "POST":
        # Extract login credentials from form
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        remember_me = request.POST.get("remember_me", False)

        # Get client information for security logging
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        # Basic validation
        if not email or not password:
            messages.error(request, "Please provide both email and password.")
            _log_login_attempt(
                email, False, ip_address, user_agent, "missing_credentials"
            )
            return render(request, "auth/login.html", {"next": next_url})

        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Please enter a valid email address.")
            _log_login_attempt(
                email, False, ip_address, user_agent, "invalid_email_format"
            )
            return render(request, "auth/login.html", {"next": next_url})

        # Check for too many failed attempts from this IP
        if _is_ip_blocked(ip_address):
            messages.error(
                request, "Too many failed login attempts. Please try again later."
            )
            _log_login_attempt(
                email, False, ip_address, user_agent, "too_many_attempts"
            )
            return render(request, "auth/login.html", {"next": next_url})

        # Attempt authentication
        user = authenticate(request, username=email, password=password)

        if user is not None:
            # Check if user account is active
            if not user.is_active:
                messages.error(
                    request, "Your account has been disabled. Please contact support."
                )
                _log_login_attempt(
                    email, False, ip_address, user_agent, "account_disabled"
                )
                return render(request, "auth/login.html", {"next": next_url})

            # Check if email is verified (optional requirement)
            if (
                hasattr(user, "email_verified")
                and not user.email_verified
                and settings.REQUIRE_EMAIL_VERIFICATION
            ):
                messages.error(
                    request, "Please verify your email address before logging in."
                )
                _log_login_attempt(
                    email, False, ip_address, user_agent, "email_not_verified"
                )
                return render(request, "auth/login.html", {"next": next_url})

            # Successful login
            login(request, user)

            # Set session expiry based on "remember me"
            if not remember_me:
                # Session expires when browser closes
                request.session.set_expiry(0)
            else:
                # Session expires in 30 days
                request.session.set_expiry(timedelta(days=30))

            # Update user's last login information
            user.last_login_ip = ip_address
            user.save(update_fields=["last_login", "last_login_ip"])

            # Log successful attempt
            _log_login_attempt(email, True, ip_address, user_agent, user=user)

            # Success message
            messages.success(request, f"Welcome back, {user.get_short_name()}!")

            # Redirect to intended page or home
            if next_url and is_safe_url(next_url, request.get_host()):
                return redirect(next_url)
            return redirect("home")

        else:
            # Failed authentication
            messages.error(request, "Invalid email or password.")
            _log_login_attempt(
                email, False, ip_address, user_agent, "invalid_credentials"
            )

    return render(request, "auth/login.html", {"next": next_url})


@csrf_protect
@require_http_methods(["GET", "POST"])
def register_view(request):
    """
    Handle user registration with email/password

    Features:
    - Email uniqueness validation
    - Password strength requirements
    - Automatic profile creation
    - Email verification initiation

    GET: Display registration form
    POST: Process registration
    """
    # Redirect authenticated users away from registration page
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        # Extract registration data
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        terms_accepted = request.POST.get("terms_accepted", False)

        # Basic validation
        errors = []

        # Required fields validation
        if not all([username, email, password, password_confirm]):
            errors.append("Please fill in all required fields.")

        # Email format validation
        if email:
            try:
                validate_email(email)
            except ValidationError:
                errors.append("Please enter a valid email address.")

        # Password confirmation
        if password != password_confirm:
            errors.append("Passwords do not match.")

        # Password strength validation
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")

        # Terms acceptance (if required)
        if settings.REQUIRE_TERMS_ACCEPTANCE and not terms_accepted:
            errors.append("You must accept the terms and conditions.")

        # Check if username already exists
        if username and User.objects.filter(username__iexact=username).exists():
            errors.append("Username already exists. Please choose a different one.")

        # Check if email already exists
        if email and User.objects.filter(email__iexact=email).exists():
            errors.append(
                "Email already registered. Please use a different email or try logging in."
            )

        # If there are validation errors, show them
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(
                request,
                "auth/register.html",
                {
                    "username": username,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                },
            )

        # Create user account with transaction to ensure data consistency
        try:
            with transaction.atomic():
                # Create the user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )

                # Create associated user profile
                profile = UserProfile.objects.create(
                    user=user, created_at=timezone.now()
                )

                # Create customer profile - this will be handled by the signal
                # but we can add additional logic here if needed
                try:
                    from customers.models import Customer

                    customer, created = Customer.objects.get_or_create(
                        user=user,
                        defaults={
                            "init_email": email,
                            "init_email_confirmed": False,  # Will be confirmed via email
                            "subscription_status": "none",
                        },
                    )
                    if created:
                        logger.info(
                            f"Customer profile created during registration: {email}"
                        )
                except ImportError:
                    # Customer model not available - signals will handle it
                    logger.info(
                        f"Customer profile will be created via signals for: {email}"
                    )

                # Log successful registration
                logger.info(
                    f"New user registered: {email} (username: {username}, customer: {customer.id if 'customer' in locals() else 'pending'})"
                )

                # Send verification email (if email verification is enabled)
                if settings.ENABLE_EMAIL_VERIFICATION:
                    # This would integrate with your email service
                    # send_verification_email(user)
                    messages.success(
                        request,
                        "Account created successfully! Please check your email to verify your account and complete the setup.",
                    )
                else:
                    # If email verification is disabled, mark as verified
                    if hasattr(user, "email_verified"):
                        user.email_verified = True
                        user.save(update_fields=["email_verified"])

                    # Update customer email confirmation
                    if "customer" in locals():
                        customer.init_email_confirmed = True
                        customer.save(update_fields=["init_email_confirmed"])

                    messages.success(
                        request,
                        "Account created successfully! You can now log in and explore your dashboard.",
                    )

                # Redirect to appropriate page
                if settings.ENABLE_EMAIL_VERIFICATION:
                    return redirect("auth:login")
                else:
                    # Auto-login if email verification is disabled
                    user = authenticate(request, username=email, password=password)
                    if user:
                        login(request, user)
                        return redirect("customers:dashboard")
                    else:
                        return redirect("auth:login")

        except Exception as e:
            # Log the error for debugging
            logger.error(f"Registration failed for {email}: {str(e)}")
            messages.error(
                request,
                "An error occurred while creating your account. Please try again or contact support.",
            )

    return render(request, "auth/register.html", {})


@login_required
@require_http_methods(["POST"])
def logout_view(request):
    """
    Handle user logout

    Features:
    - Secure session cleanup
    - Logout logging
    - Redirect to appropriate page
    """
    user_email = request.user.email if request.user.is_authenticated else "Unknown"

    # Log the logout
    logger.info(f"User logged out: {user_email}")

    # Clear the session and log out
    logout(request)

    # Success message
    messages.success(request, "You have been successfully logged out.")

    # Redirect to home page or login page
    next_url = request.GET.get("next", "/")
    if next_url and is_safe_url(next_url, request.get_host()):
        return redirect(next_url)

    return redirect("home")


@login_required
@require_http_methods(["GET", "POST"])
def profile_view(request):
    """
    Display and update user profile information

    Features:
    - View current profile data
    - Update profile information
    - Customer account integration
    - Subscription status display
    """
    user = request.user
    profile, created = UserProfile.objects.get_or_create(user=user)

    # Get or create customer profile
    customer = None
    try:
        from customers.models import Customer

        customer, customer_created = Customer.objects.get_or_create(
            user=user,
            defaults={
                "init_email": user.email,
                "init_email_confirmed": getattr(user, "email_verified", False),
            },
        )
        if customer_created:
            logger.info(f"Customer profile created in profile view for: {user.email}")
    except ImportError:
        logger.warning("Customer model not available in profile view")

    if request.method == "POST":
        # Handle avatar upload/removal
        if "avatar" in request.FILES:
            profile.avatar = request.FILES["avatar"]
        elif request.POST.get("remove_avatar") == "true":
            if profile.avatar:
                profile.avatar.delete()
                profile.avatar = None

        # Update profile information
        user.first_name = request.POST.get("first_name", "").strip()
        user.last_name = request.POST.get("last_name", "").strip()
        user.receive_marketing_emails = bool(
            request.POST.get("receive_marketing_emails")
        )

        profile.bio = request.POST.get("bio", "").strip()[:500]  # Limit bio length
        profile.phone_number = request.POST.get("phone_number", "").strip()
        profile.country = request.POST.get("country", "").strip()
        profile.timezone = request.POST.get("timezone", "UTC")
        profile.language_preference = request.POST.get("language_preference", "en")
        profile.email_notifications = bool(request.POST.get("email_notifications"))
        profile.push_notifications = bool(request.POST.get("push_notifications"))

        try:
            with transaction.atomic():
                user.save()
                profile.save()

                # Sync customer data if available
                if customer and customer.stripe_id:
                    try:
                        # Update customer metadata in Stripe
                        metadata = {
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "country": profile.country,
                            "timezone": profile.timezone,
                            "phone": profile.phone_number,
                        }
                        # This would call your Stripe update function
                        # helpers.billing.update_customer(customer.stripe_id, metadata=metadata)
                        customer.last_stripe_sync = timezone.now()
                        customer.save(update_fields=["last_stripe_sync"])
                    except Exception as e:
                        logger.error(
                            f"Failed to sync customer data with Stripe: {str(e)}"
                        )
                        # Don't fail the profile update if Stripe sync fails

                messages.success(request, "Profile updated successfully!")
                logger.info(f"Profile updated for user: {user.email}")

        except Exception as e:
            logger.error(f"Profile update failed for {user.email}: {str(e)}")
            messages.error(request, "Failed to update profile. Please try again.")

    context = {
        "user": user,
        "profile": profile,
        "customer": customer,
        "timezones": [
            ("UTC", "UTC"),
            ("US/Eastern", "Eastern Time (UTC-5)"),
            ("US/Central", "Central Time (UTC-6)"),
            ("US/Mountain", "Mountain Time (UTC-7)"),
            ("US/Pacific", "Pacific Time (UTC-8)"),
            ("Europe/London", "London (UTC+0)"),
            ("Europe/Paris", "Paris (UTC+1)"),
            ("Europe/Berlin", "Berlin (UTC+1)"),
            ("Asia/Tokyo", "Tokyo (UTC+9)"),
            ("Asia/Shanghai", "Shanghai (UTC+8)"),
            ("Asia/Kolkata", "India (UTC+5:30)"),
            ("Australia/Sydney", "Sydney (UTC+10)"),
        ],
        "languages": [
            ("en", "English"),
            ("es", "Spanish"),
            ("fr", "French"),
            ("de", "German"),
            ("it", "Italian"),
            ("pt", "Portuguese"),
            ("hi", "Hindi"),
            ("zh", "Chinese"),
            ("ja", "Japanese"),
            ("ko", "Korean"),
        ],
    }

    # Add customer-specific context
    if customer:
        context.update(
            {
                "has_customer_profile": True,
                "subscription_status": customer.subscription_status,
                "has_active_subscription": customer.has_active_subscription,
                "stripe_customer_exists": bool(customer.stripe_id),
                "customer_since": customer.customer_since,
                "lifetime_value": customer.lifetime_value,
            }
        )
    else:
        context["has_customer_profile"] = False

    return render(request, "auth/profile.html", context)


@login_required
@require_http_methods(["POST"])
def change_password_view(request):
    """
    Handle password changes for authenticated users

    Features:
    - Current password verification
    - New password strength validation
    - Session invalidation for security
    """
    current_password = request.POST.get("current_password", "")
    new_password = request.POST.get("new_password", "")
    new_password_confirm = request.POST.get("new_password_confirm", "")

    # Validation
    if not all([current_password, new_password, new_password_confirm]):
        messages.error(request, "Please fill in all password fields.")
        return redirect("auth:profile")

    # Verify current password
    if not request.user.check_password(current_password):
        messages.error(request, "Current password is incorrect.")
        return redirect("auth:profile")

    # Check new password confirmation
    if new_password != new_password_confirm:
        messages.error(request, "New passwords do not match.")
        return redirect("auth:profile")

    # Password strength validation
    if len(new_password) < 8:
        messages.error(request, "New password must be at least 8 characters long.")
        return redirect("auth:profile")

    try:
        # Change password
        request.user.set_password(new_password)
        request.user.save()

        # Log password change
        logger.info(f"Password changed for user: {request.user.email}")

        messages.success(request, "Password changed successfully! Please log in again.")

        # Logout user to force re-authentication with new password
        logout(request)
        return redirect("auth:login")

    except Exception as e:
        logger.error(f"Password change failed for {request.user.email}: {str(e)}")
        messages.error(request, "Failed to change password. Please try again.")

    return redirect("auth:profile")


def _log_login_attempt(
    email, success, ip_address, user_agent, failure_reason=None, user=None
):
    """
    Log login attempts for security monitoring

    Args:
        email: Email address used in attempt
        success: Whether login was successful
        ip_address: Client IP address
        user_agent: Browser user agent
        failure_reason: Reason for failure (if applicable)
        user: User object (if login was successful)
    """
    try:
        LoginAttempt.objects.create(
            user=user,
            email_attempted=email,
            success=success,
            failure_reason=failure_reason or "",
            ip_address=ip_address,
            user_agent=user_agent,
            attempted_at=timezone.now(),
        )
    except Exception as e:
        # Don't let logging errors break the login flow
        logger.error(f"Failed to log login attempt: {str(e)}")


def _is_ip_blocked(ip_address, max_attempts=5, window_minutes=15):
    """
    Check if an IP address should be blocked due to too many failed attempts

    Args:
        ip_address: IP address to check
        max_attempts: Maximum failed attempts allowed
        window_minutes: Time window to check attempts within

    Returns:
        bool: True if IP should be blocked
    """
    try:
        # Check failed attempts in the last window_minutes
        since = timezone.now() - timedelta(minutes=window_minutes)
        failed_attempts = LoginAttempt.objects.filter(
            ip_address=ip_address, success=False, attempted_at__gte=since
        ).count()

        return failed_attempts >= max_attempts

    except Exception as e:
        logger.error(f"Error checking IP block status: {str(e)}")
        return False  # Don't block if we can't check


@require_http_methods(["POST"])
def check_email_availability(request):
    """
    AJAX endpoint to check if email is available during registration

    Returns JSON response with availability status
    """
    email = request.POST.get("email", "").strip().lower()

    if not email:
        return JsonResponse({"available": False, "message": "Email is required"})

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"available": False, "message": "Invalid email format"})

    exists = User.objects.filter(email__iexact=email).exists()

    return JsonResponse(
        {
            "available": not exists,
            "message": (
                "Email is available" if not exists else "Email already registered"
            ),
        }
    )


@require_http_methods(["POST"])
def check_username_availability(request):
    """
    AJAX endpoint to check if username is available during registration

    Returns JSON response with availability status
    """
    username = request.POST.get("username", "").strip()

    if not username:
        return JsonResponse({"available": False, "message": "Username is required"})

    if len(username) < 3:
        return JsonResponse(
            {"available": False, "message": "Username must be at least 3 characters"}
        )

    exists = User.objects.filter(username__iexact=username).exists()

    return JsonResponse(
        {
            "available": not exists,
            "message": (
                "Username is available" if not exists else "Username already taken"
            ),
        }
    )

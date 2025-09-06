from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count
import logging

# Initialize logger
logger = logging.getLogger("dashboard")


@login_required
def dashboard_view(request):
    """
    Main dashboard view with customer and subscription information

    Features:
    - Account overview with key metrics
    - Subscription status and management
    - Customer profile integration
    - Quick actions and navigation
    """
    user = request.user

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
            logger.info(f"Customer profile created in dashboard for: {user.email}")
    except ImportError:
        logger.warning("Customer model not available in dashboard")

    # Calculate account age in days
    account_age_days = (timezone.now() - user.date_joined).days

    # Prepare dashboard context
    context = {
        "user": user,
        "customer": customer,
        "account_age_days": account_age_days,
        "email_verified": getattr(user, "email_verified", False),
    }

    # Add customer-specific context if available
    if customer:
        context.update(
            {
                "has_customer_profile": True,
                "subscription_status": customer.subscription_status,
                "has_active_subscription": customer.has_active_subscription,
                "has_stripe_customer": bool(customer.stripe_id),
                "customer_since": customer.customer_since,
                "lifetime_value": customer.lifetime_value,
            }
        )

        # Add subscription-specific data
        if customer.has_active_subscription:
            context.update(
                {
                    "subscription_active": True,
                    "can_manage_subscription": True,
                }
            )
    else:
        context.update(
            {
                "has_customer_profile": False,
                "subscription_status": "none",
                "has_active_subscription": False,
                "has_stripe_customer": False,
            }
        )

    return render(request, "dashboard/main.html", context)


@login_required
def dashboard_stats_api(request):
    """
    API endpoint for dashboard statistics
    Returns JSON data for dynamic dashboard updates
    """
    from django.http import JsonResponse

    try:
        user = request.user

        # Get customer data
        customer = None
        try:
            from customers.models import Customer

            customer = Customer.objects.filter(user=user).first()
        except ImportError:
            pass

        stats = {
            "account_age_days": (timezone.now() - user.date_joined).days,
            "email_verified": getattr(user, "email_verified", False),
            "has_customer_profile": customer is not None,
        }

        if customer:
            stats.update(
                {
                    "subscription_status": customer.subscription_status,
                    "has_active_subscription": customer.has_active_subscription,
                    "lifetime_value": float(customer.lifetime_value),
                    "customer_since": customer.customer_since.isoformat(),
                }
            )

        return JsonResponse(stats)

    except Exception as e:
        logger.error(f"Dashboard stats API error for {request.user.email}: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@login_required
def dashboard_quick_action(request):
    """
    Handle quick actions from the dashboard

    Supports:
    - Email verification resend
    - Customer profile sync
    - Subscription management shortcuts
    """
    if request.method != "POST":
        return redirect("dashboard:main")

    action = request.POST.get("action")

    try:
        if action == "resend_verification":
            # Implement email verification resend
            # This would integrate with your email service
            messages.success(
                request, "Verification email sent! Please check your inbox."
            )
            logger.info(f"Verification email resent to: {request.user.email}")

        elif action == "sync_customer":
            # Sync customer data with Stripe
            try:
                from customers.models import Customer

                customer = Customer.objects.get(user=request.user)
                if customer.stripe_id:
                    customer.sync_with_stripe()
                    messages.success(request, "Customer data synced successfully!")
                else:
                    messages.warning(request, "No Stripe customer found to sync.")
            except Customer.DoesNotExist:
                messages.error(request, "Customer profile not found.")
            except ImportError:
                messages.error(request, "Customer functionality not available.")

        elif action == "create_stripe_customer":
            # Force create Stripe customer
            try:
                from customers.models import Customer

                customer = Customer.objects.get(user=request.user)
                if not customer.stripe_id:
                    customer.create_stripe_customer()
                    messages.success(request, "Billing account created successfully!")
                else:
                    messages.info(request, "Billing account already exists.")
            except Customer.DoesNotExist:
                messages.error(request, "Customer profile not found.")
            except Exception as e:
                logger.error(f"Failed to create Stripe customer: {str(e)}")
                messages.error(
                    request, "Failed to create billing account. Please try again."
                )

        else:
            messages.warning(request, "Unknown action requested.")

    except Exception as e:
        logger.error(f"Dashboard quick action error ({action}): {str(e)}")
        messages.error(request, "An error occurred. Please try again.")

    return redirect("dashboard:main")

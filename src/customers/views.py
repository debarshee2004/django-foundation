from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.conf import settings
import logging
import json

from .models import Customer
from auth.models import CustomUser

# Initialize logger
logger = logging.getLogger("customers")


# ============================================================================
# CUSTOMER DASHBOARD VIEWS
# ============================================================================


@login_required
@require_http_methods(["GET"])
def customer_dashboard(request):
    """
    Main customer dashboard showing account overview and subscription status

    Features:
    - Account status overview
    - Subscription information
    - Recent activity
    - Quick actions
    """
    try:
        # Get or create customer profile
        customer, created = Customer.objects.get_or_create(
            user=request.user,
            defaults={
                "init_email": request.user.email,
                "init_email_confirmed": getattr(request.user, "email_verified", False),
            },
        )

        if created:
            logger.info(
                f"Customer profile created for existing user: {request.user.email}"
            )

        # Prepare dashboard context
        context = {
            "customer": customer,
            "user": request.user,
            "has_stripe_customer": bool(customer.stripe_id),
            "subscription_status": customer.subscription_status,
            "account_age_days": (timezone.now() - customer.created_at).days,
            "email_verified": getattr(request.user, "email_verified", False),
        }

        # Add subscription-specific data
        if customer.has_active_subscription:
            context.update(
                {
                    "subscription_active": True,
                    "lifetime_value": customer.lifetime_value,
                }
            )

        # Redirect to main dashboard instead of separate customer dashboard
        # The main dashboard now includes all customer functionality
        return redirect("dashboard:main")

    except Exception as e:
        logger.error(
            f"Error loading customer dashboard for {request.user.email}: {str(e)}"
        )
        messages.error(request, "Unable to load dashboard. Please try again.")
        return redirect("home")


@login_required
@require_http_methods(["GET"])
def billing_portal(request):
    """
    Customer billing portal for managing subscriptions and payment methods

    Features:
    - View current subscription
    - Manage payment methods
    - Download invoices
    - Update billing information
    """
    try:
        customer = get_object_or_404(Customer, user=request.user)

        if not customer.stripe_id:
            messages.warning(
                request, "No billing account found. Please contact support."
            )
            return redirect("customers:dashboard")

        # Get billing information from Stripe
        try:
            # This would call your Stripe integration
            billing_info = customer.sync_with_stripe()

            context = {
                "customer": customer,
                "billing_info": billing_info,
                "can_manage_billing": True,
            }

            return render(request, "customers/billing.html", context)

        except Exception as e:
            logger.error(
                f"Failed to load billing info for {request.user.email}: {str(e)}"
            )
            messages.error(
                request, "Unable to load billing information. Please try again."
            )
            return redirect("customers:dashboard")

    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found.")
        return redirect("customers:dashboard")


@login_required
@require_http_methods(["POST"])
def sync_customer_data(request):
    """
    Manually sync customer data with Stripe

    Features:
    - Force sync with Stripe
    - Update local customer data
    - Return JSON response for AJAX calls
    """
    try:
        customer = get_object_or_404(Customer, user=request.user)

        if not customer.stripe_id:
            return JsonResponse(
                {"success": False, "error": "No Stripe customer ID found"}
            )

        # Sync with Stripe
        stripe_data = customer.sync_with_stripe()

        return JsonResponse(
            {
                "success": True,
                "message": "Customer data synced successfully",
                "last_sync": (
                    customer.last_stripe_sync.isoformat()
                    if customer.last_stripe_sync
                    else None
                ),
            }
        )

    except Customer.DoesNotExist:
        return JsonResponse({"success": False, "error": "Customer profile not found"})
    except Exception as e:
        logger.error(f"Failed to sync customer data for {request.user.email}: {str(e)}")
        return JsonResponse({"success": False, "error": "Failed to sync customer data"})


# ============================================================================
# SUBSCRIPTION MANAGEMENT VIEWS
# ============================================================================


@login_required
@require_http_methods(["GET", "POST"])
def subscription_management(request):
    """
    Subscription management interface

    Features:
    - View current subscription details
    - Change subscription plans
    - Cancel subscription
    - Pause/resume subscription
    """
    try:
        customer = get_object_or_404(Customer, user=request.user)

        if request.method == "POST":
            action = request.POST.get("action")

            if action == "cancel_subscription":
                return handle_subscription_cancellation(request, customer)
            elif action == "pause_subscription":
                return handle_subscription_pause(request, customer)
            elif action == "resume_subscription":
                return handle_subscription_resume(request, customer)
            elif action == "change_plan":
                return handle_plan_change(request, customer)

        context = {
            "customer": customer,
            "subscription_status": customer.subscription_status,
            "can_cancel": customer.subscription_status in ["active", "trial"],
            "can_pause": customer.subscription_status == "active",
            "can_resume": customer.subscription_status == "paused",
        }

        return render(request, "customers/subscription.html", context)

    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found.")
        return redirect("customers:dashboard")


def handle_subscription_cancellation(request, customer):
    """Handle subscription cancellation request"""
    try:
        # Add cancellation logic here
        # This would integrate with your Stripe subscription management

        customer.update_subscription_status("canceled")
        messages.success(request, "Your subscription has been canceled.")

        logger.info(f"Subscription canceled for customer: {customer.user.email}")

    except Exception as e:
        logger.error(
            f"Failed to cancel subscription for {customer.user.email}: {str(e)}"
        )
        messages.error(request, "Failed to cancel subscription. Please try again.")

    return redirect("customers:subscription")


def handle_subscription_pause(request, customer):
    """Handle subscription pause request"""
    try:
        # Add pause logic here
        customer.update_subscription_status("paused")
        messages.success(request, "Your subscription has been paused.")

        logger.info(f"Subscription paused for customer: {customer.user.email}")

    except Exception as e:
        logger.error(
            f"Failed to pause subscription for {customer.user.email}: {str(e)}"
        )
        messages.error(request, "Failed to pause subscription. Please try again.")

    return redirect("customers:subscription")


def handle_subscription_resume(request, customer):
    """Handle subscription resume request"""
    try:
        # Add resume logic here
        customer.update_subscription_status("active")
        messages.success(request, "Your subscription has been resumed.")

        logger.info(f"Subscription resumed for customer: {customer.user.email}")

    except Exception as e:
        logger.error(
            f"Failed to resume subscription for {customer.user.email}: {str(e)}"
        )
        messages.error(request, "Failed to resume subscription. Please try again.")

    return redirect("customers:subscription")


def handle_plan_change(request, customer):
    """Handle subscription plan change request"""
    new_plan = request.POST.get("new_plan")

    if not new_plan:
        messages.error(request, "Please select a plan.")
        return redirect("customers:subscription")

    try:
        # Add plan change logic here
        # This would integrate with your Stripe subscription management

        messages.success(request, f"Your plan has been changed to {new_plan}.")
        logger.info(f"Plan changed for customer {customer.user.email}: {new_plan}")

    except Exception as e:
        logger.error(f"Failed to change plan for {customer.user.email}: {str(e)}")
        messages.error(request, "Failed to change plan. Please try again.")

    return redirect("customers:subscription")


# ============================================================================
# CUSTOMER SUPPORT VIEWS
# ============================================================================


@login_required
@require_http_methods(["GET", "POST"])
def support_center(request):
    """
    Customer support center

    Features:
    - Submit support tickets
    - View ticket history
    - Knowledge base access
    - Contact information
    """
    try:
        customer = get_object_or_404(Customer, user=request.user)

        if request.method == "POST":
            # Handle support ticket submission
            subject = request.POST.get("subject", "").strip()
            message = request.POST.get("message", "").strip()
            priority = request.POST.get("priority", "medium")

            if not subject or not message:
                messages.error(request, "Please provide both subject and message.")
                return render(request, "customers/support.html", {"customer": customer})

            try:
                # Create support ticket (integrate with your ticketing system)
                ticket_data = {
                    "customer_id": customer.id,
                    "user_email": customer.user.email,
                    "subject": subject,
                    "message": message,
                    "priority": priority,
                    "stripe_customer_id": customer.stripe_id,
                }

                # This would create a ticket in your support system
                # ticket_id = create_support_ticket(ticket_data)

                messages.success(
                    request,
                    "Support ticket submitted successfully. We'll get back to you soon!",
                )
                logger.info(
                    f"Support ticket created for customer: {customer.user.email}"
                )

                return redirect("customers:support")

            except Exception as e:
                logger.error(
                    f"Failed to create support ticket for {customer.user.email}: {str(e)}"
                )
                messages.error(
                    request, "Failed to submit support ticket. Please try again."
                )

        context = {
            "customer": customer,
            "subscription_status": customer.subscription_status,
        }

        return render(request, "customers/support.html", context)

    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found.")
        return redirect("customers:dashboard")


# ============================================================================
# API ENDPOINTS FOR FRONTEND INTEGRATION
# ============================================================================


@login_required
@require_http_methods(["GET"])
def customer_api_status(request):
    """
    API endpoint to get customer status information

    Returns JSON with customer and subscription status
    """
    try:
        customer = get_object_or_404(Customer, user=request.user)

        data = {
            "customer_id": customer.id,
            "stripe_id": customer.stripe_id,
            "subscription_status": customer.subscription_status,
            "has_active_subscription": customer.has_active_subscription,
            "lifetime_value": float(customer.lifetime_value),
            "customer_since": customer.customer_since.isoformat(),
            "last_sync": (
                customer.last_stripe_sync.isoformat()
                if customer.last_stripe_sync
                else None
            ),
            "email_confirmed": customer.init_email_confirmed,
        }

        return JsonResponse(data)

    except Customer.DoesNotExist:
        return JsonResponse({"error": "Customer not found"}, status=404)
    except Exception as e:
        logger.error(f"API error for customer status {request.user.email}: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_protect
@require_http_methods(["POST"])
def webhook_stripe(request):
    """
    Handle Stripe webhooks for customer and subscription events

    This endpoint processes Stripe webhooks to keep customer data in sync
    """
    try:
        # Verify webhook signature (implement based on your Stripe setup)
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        # Parse webhook event
        event = json.loads(payload.decode("utf-8"))

        # Handle the event
        from .models import handle_subscription_webhook

        success = handle_subscription_webhook(event)

        if success:
            return JsonResponse({"status": "success"})
        else:
            return JsonResponse({"status": "ignored"})

    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        return JsonResponse({"status": "error"}, status=400)


# ============================================================================
# UTILITY VIEWS
# ============================================================================


@login_required
@require_http_methods(["POST"])
def delete_customer_account(request):
    """
    Handle customer account deletion request

    Features:
    - Cancel active subscriptions
    - Delete customer data
    - Maintain audit trail
    """
    confirmation = request.POST.get("confirmation")

    if confirmation != "DELETE":
        messages.error(request, "Please type 'DELETE' to confirm account deletion.")
        return redirect("auth:profile")

    try:
        customer = get_object_or_404(Customer, user=request.user)
        user = request.user

        # Cancel active subscriptions first
        if customer.has_active_subscription:
            customer.update_subscription_status("canceled")

        # Log account deletion
        logger.warning(f"Customer account deletion requested: {user.email}")

        # Delete customer and user (implement based on your data retention policy)
        # customer.delete()
        # user.delete()

        messages.success(
            request,
            "Account deletion request processed. You will receive confirmation via email.",
        )
        return redirect("home")

    except Exception as e:
        logger.error(
            f"Failed to delete customer account {request.user.email}: {str(e)}"
        )
        messages.error(
            request, "Failed to process account deletion. Please contact support."
        )
        return redirect("auth:profile")

import helpers.billing
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import logging

from subscriptions.models import SubscriptionPrice, Subscription, UserSubscription

# Initialize logger
logger = logging.getLogger("checkouts")

User = get_user_model()
BASE_URL = settings.BASE_URL


class CheckoutError(Exception):
    """Custom exception for checkout-related errors"""

    pass


def get_customer_or_create(user):
    """
    Get or create customer profile for checkout

    Returns:
        tuple: (customer, created) where customer is the customer object
               and created is a boolean indicating if it was just created
    """
    try:
        # Try to get existing customer from our customer app
        from customers.models import Customer

        customer, created = Customer.objects.get_or_create(
            user=user,
            defaults={
                "init_email": user.email,
                "init_email_confirmed": getattr(user, "email_verified", False),
            },
        )

        # Ensure customer has Stripe ID
        if not customer.stripe_id:
            customer.create_stripe_customer()

        return customer, created

    except ImportError:
        # Fallback if customer app is not available
        logger.warning("Customer app not available, using basic user model")
        if not hasattr(user, "stripe_customer_id"):
            raise CheckoutError("User does not have customer profile configured")
        return user, False


def product_price_redirect_view(request, price_id=None, *args, **kwargs):
    """
    Enhanced price redirect with validation and error handling
    """
    if not price_id:
        messages.error(request, "Invalid pricing selection.")
        return redirect("pricing")

    try:
        # Validate that the price exists and is active
        price_obj = SubscriptionPrice.objects.select_related("subscription").get(
            id=price_id, subscription__active=True
        )

        # Store validated price information in session
        request.session["checkout_subscription_price_id"] = price_id
        request.session["checkout_price_info"] = {
            "price": str(price_obj.price),
            "interval": price_obj.interval,
            "plan_name": price_obj.display_sub_name,
        }

        logger.info(
            f"User {request.user.id if request.user.is_authenticated else 'anonymous'} selected price {price_id}"
        )
        return redirect("stripe-checkout-start")

    except SubscriptionPrice.DoesNotExist:
        logger.warning(f"Invalid price ID {price_id} selected")
        messages.error(request, "Selected plan is no longer available.")
        return redirect("pricing")
    except Exception as e:
        logger.error(f"Error in price redirect: {str(e)}")
        messages.error(request, "Unable to process your selection. Please try again.")
        return redirect("pricing")


@login_required
def checkout_redirect_view(request):
    """
    Enhanced checkout redirect with better error handling and flexibility
    """
    checkout_subscription_price_id = request.session.get(
        "checkout_subscription_price_id"
    )

    if not checkout_subscription_price_id:
        messages.error(request, "No plan selected. Please choose a plan to continue.")
        return redirect("pricing")

    try:
        # Get and validate subscription price
        price_obj = SubscriptionPrice.objects.select_related("subscription").get(
            id=checkout_subscription_price_id, subscription__active=True
        )

        if not price_obj.stripe_id:
            logger.error(f"Price {price_obj.id} missing Stripe ID")
            messages.error(
                request, "Pricing configuration error. Please contact support."
            )
            return redirect("pricing")

        # Get or create customer profile
        try:
            customer, customer_created = get_customer_or_create(request.user)
            customer_stripe_id = getattr(customer, "stripe_id", None)

            if customer_created:
                logger.info(f"Created new customer profile for user {request.user.id}")

        except CheckoutError as e:
            logger.error(
                f"Customer creation failed for user {request.user.id}: {str(e)}"
            )
            messages.error(
                request, "Unable to create customer profile. Please contact support."
            )
            return redirect("pricing")

        if not customer_stripe_id:
            logger.error(
                f"Customer {customer.id if hasattr(customer, 'id') else 'unknown'} missing Stripe ID"
            )
            messages.error(
                request, "Customer profile incomplete. Please contact support."
            )
            return redirect("pricing")

        # Prepare checkout session URLs
        success_url_path = reverse("stripe-checkout-end")
        pricing_url_path = reverse("pricing")
        success_url = f"{BASE_URL}{success_url_path}"
        cancel_url = f"{BASE_URL}{pricing_url_path}"

        # Check for existing subscription and handle billing cycle anchor
        billing_cycle_anchor = None
        try:
            existing_sub = UserSubscription.objects.get(user=request.user)
            if existing_sub.is_active_status and existing_sub.current_period_end:
                billing_cycle_anchor = existing_sub.billing_cycle_anchor
                logger.info(
                    f"Using billing cycle anchor for user {request.user.id}: {billing_cycle_anchor}"
                )
        except UserSubscription.DoesNotExist:
            pass

        # Start Stripe checkout session
        try:
            checkout_url = helpers.billing.start_checkout_session(
                customer_stripe_id,
                success_url=success_url,
                cancel_url=cancel_url,
                price_stripe_id=str(price_obj.stripe_id),
                billing_cycle_anchor=billing_cycle_anchor,
                raw=False,
            )

            logger.info(
                f"Created checkout session for user {request.user.id}, price {price_obj.id}"
            )
            return redirect(checkout_url)

        except Exception as e:
            logger.error(f"Stripe checkout session creation failed: {str(e)}")
            messages.error(
                request, "Unable to start checkout session. Please try again."
            )
            return redirect("pricing")

    except SubscriptionPrice.DoesNotExist:
        logger.warning(f"Price {checkout_subscription_price_id} not found or inactive")
        messages.error(request, "Selected plan is no longer available.")
        # Clear invalid session data
        if "checkout_subscription_price_id" in request.session:
            del request.session["checkout_subscription_price_id"]
        if "checkout_price_info" in request.session:
            del request.session["checkout_price_info"]
        return redirect("pricing")

    except Exception as e:
        logger.error(f"Unexpected error in checkout redirect: {str(e)}")
        messages.error(request, "An unexpected error occurred. Please try again.")
        return redirect("pricing")


def checkout_finalize_view(request):
    """
    Enhanced checkout finalization with better error handling and logging
    """
    session_id = request.GET.get("session_id")

    if not session_id:
        logger.warning("Checkout finalize called without session_id")
        messages.error(request, "Invalid checkout session. Please try again.")
        return redirect("pricing")

    try:
        # Get checkout data from Stripe
        checkout_data = helpers.billing.get_checkout_customer_plan(session_id)

        if not checkout_data or not isinstance(checkout_data, dict):
            logger.error(f"Invalid checkout data for session {session_id}")
            messages.error(
                request,
                "Unable to retrieve checkout information. Please contact support.",
            )
            return redirect("pricing")

        # Extract required data
        plan_id = checkout_data.pop("plan_id", None)
        customer_id = checkout_data.pop("customer_id", None)
        sub_stripe_id = checkout_data.pop("sub_stripe_id", None)
        subscription_data = {**checkout_data}

        if not all([plan_id, customer_id, sub_stripe_id]):
            logger.error(
                f"Incomplete checkout data: plan_id={plan_id}, customer_id={customer_id}, sub_stripe_id={sub_stripe_id}"
            )
            messages.error(request, "Incomplete checkout data. Please contact support.")
            return redirect("pricing")

        # Get subscription object
        try:
            subscription_obj = Subscription.objects.get(
                subscriptionprice__stripe_id=plan_id
            )
        except Subscription.DoesNotExist:
            logger.error(f"Subscription not found for plan_id {plan_id}")
            messages.error(
                request, "Invalid subscription plan. Please contact support."
            )
            return redirect("pricing")
        except Subscription.MultipleObjectsReturned:
            logger.error(f"Multiple subscriptions found for plan_id {plan_id}")
            messages.error(
                request, "Subscription configuration error. Please contact support."
            )
            return redirect("pricing")

        # Get user object
        try:
            user_obj = User.objects.get(customer__stripe_id=customer_id)
        except User.DoesNotExist:
            logger.error(f"User not found for customer_id {customer_id}")
            messages.error(request, "Customer not found. Please contact support.")
            return redirect("pricing")
        except Exception as e:
            logger.error(
                f"Error retrieving user for customer_id {customer_id}: {str(e)}"
            )
            messages.error(
                request, "Error retrieving customer. Please contact support."
            )
            return redirect("pricing")

        # Process subscription update/creation
        return process_user_subscription_update(
            user_obj=user_obj,
            subscription_obj=subscription_obj,
            sub_stripe_id=sub_stripe_id,
            subscription_data=subscription_data,
            request=request,
        )

    except Exception as e:
        logger.error(f"Unexpected error in checkout finalize: {str(e)}")
        messages.error(
            request,
            "An unexpected error occurred during checkout completion. Please contact support.",
        )
        return redirect("pricing")


def process_user_subscription_update(
    user_obj, subscription_obj, sub_stripe_id, subscription_data, request
):
    """
    Process user subscription creation or update with enhanced error handling

    Args:
        user_obj: User instance
        subscription_obj: Subscription instance
        sub_stripe_id: Stripe subscription ID
        subscription_data: Additional subscription data from Stripe
        request: HTTP request object

    Returns:
        HttpResponse: Redirect or rendered response
    """
    try:
        updated_sub_options = {
            "subscription": subscription_obj,
            "stripe_id": sub_stripe_id,
            "user_cancelled": False,
            **subscription_data,
        }

        user_sub_obj, user_sub_created = UserSubscription.objects.get_or_create(
            user=user_obj, defaults=updated_sub_options
        )

        if not user_sub_created:
            # Handle existing subscription update
            old_stripe_id = user_sub_obj.stripe_id
            same_stripe_id = sub_stripe_id == old_stripe_id

            # Cancel old subscription if different
            if old_stripe_id and not same_stripe_id:
                try:
                    helpers.billing.cancel_subscription(
                        old_stripe_id,
                        reason="Auto ended, new membership",
                        feedback="other",
                    )
                    logger.info(
                        f"Cancelled old subscription {old_stripe_id} for user {user_obj.id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to cancel old subscription {old_stripe_id}: {str(e)}"
                    )
                    # Continue despite cancellation failure

            # Update with new subscription data
            for k, v in updated_sub_options.items():
                setattr(user_sub_obj, k, v)
            user_sub_obj.save()

            logger.info(f"Updated subscription for user {user_obj.id}: {sub_stripe_id}")
        else:
            logger.info(
                f"Created new subscription for user {user_obj.id}: {sub_stripe_id}"
            )

        # Clear checkout session data
        if "checkout_subscription_price_id" in request.session:
            del request.session["checkout_subscription_price_id"]
        if "checkout_price_info" in request.session:
            del request.session["checkout_price_info"]

        # Success message and redirect
        messages.success(
            request,
            f"Welcome to {subscription_obj.name}! Your subscription is now active.",
        )

        # Redirect to user's subscription management page or dashboard
        if hasattr(user_sub_obj, "get_absolute_url"):
            return redirect(user_sub_obj.get_absolute_url())
        else:
            return redirect("dashboard:main")

    except Exception as e:
        logger.error(
            f"Error processing subscription update for user {user_obj.id}: {str(e)}"
        )
        messages.error(
            request, "Error completing subscription setup. Please contact support."
        )
        return redirect("pricing")


@require_http_methods(["GET"])
def checkout_status_api(request):
    """
    API endpoint to check checkout status
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        user_sub = UserSubscription.objects.get(user=request.user)
        return JsonResponse(
            {
                "has_subscription": True,
                "plan_name": user_sub.plan_name,
                "status": user_sub.status,
                "is_active": user_sub.is_active_status,
            }
        )
    except UserSubscription.DoesNotExist:
        return JsonResponse(
            {
                "has_subscription": False,
                "plan_name": None,
                "status": None,
                "is_active": False,
            }
        )
    except Exception as e:
        logger.error(f"Error in checkout status API: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)

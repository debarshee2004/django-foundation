import helpers.billing
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse

from subscriptions.models import SubscriptionPrice, UserSubscription
from subscriptions import utils as subs_utils


import helpers.billing
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
import logging

from subscriptions.models import SubscriptionPrice, UserSubscription, Subscription
from subscriptions import utils as subs_utils

# Initialize logger
logger = logging.getLogger("subscriptions")


@login_required
def user_subscription_view(request):
    """
    Enhanced user subscription management view with better UX
    """
    user_sub_obj, created = UserSubscription.objects.get_or_create(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action", "refresh")

        if action == "refresh":
            try:
                finished = subs_utils.refresh_active_users_subscriptions(
                    user_ids=[request.user.id], active_only=False
                )
                if finished:
                    messages.success(
                        request, "Your subscription details have been updated."
                    )
                    logger.info(f"Refreshed subscription for user {request.user.id}")
                else:
                    messages.warning(
                        request,
                        "Unable to refresh subscription details. Please try again.",
                    )
                    logger.warning(
                        f"Failed to refresh subscription for user {request.user.id}"
                    )
            except Exception as e:
                logger.error(
                    f"Error refreshing subscription for user {request.user.id}: {str(e)}"
                )
                messages.error(
                    request, "An error occurred while refreshing. Please try again."
                )

        return redirect(user_sub_obj.get_absolute_url())

    # Get available plans for upgrade/downgrade options
    available_plans = (
        SubscriptionPrice.objects.filter(subscription__active=True, featured=True)
        .select_related("subscription")
        .order_by("subscription__order", "price")
    )

    context = {
        "subscription": user_sub_obj,
        "available_plans": available_plans,
        "can_upgrade": user_sub_obj.subscription is not None,
        "is_new_subscription": created,
    }

    return render(request, "subscriptions/user_details_view.html", context)


@login_required
def user_subscription_cancel_view(request):
    """
    Enhanced subscription cancellation with better UX and options
    """
    user_sub_obj, created = UserSubscription.objects.get_or_create(user=request.user)

    if request.method == "POST":
        cancel_type = request.POST.get("cancel_type", "end_of_period")
        reason = request.POST.get("reason", "User wanted to end")
        feedback = request.POST.get("feedback", "other")

        if user_sub_obj.stripe_id and user_sub_obj.is_active_status:
            try:
                # Determine cancellation timing
                cancel_immediately = cancel_type == "immediate"
                cancel_at_period_end = not cancel_immediately

                sub_data = helpers.billing.cancel_subscription(
                    user_sub_obj.stripe_id,
                    reason=reason,
                    feedback=feedback,
                    cancel_at_period_end=cancel_at_period_end,
                    raw=False,
                )

                # Update local subscription data
                if isinstance(sub_data, dict):
                    for k, v in sub_data.items():
                        setattr(user_sub_obj, k, v)
                    user_sub_obj.save()

                # Provide appropriate success message
                if cancel_immediately:
                    messages.success(
                        request,
                        "Your subscription has been cancelled and access has ended.",
                    )
                else:
                    end_date = user_sub_obj.current_period_end
                    if end_date:
                        messages.success(
                            request,
                            f"Your subscription will be cancelled at the end of your current billing period ({end_date.strftime('%B %d, %Y')}). You'll continue to have access until then.",
                        )
                    else:
                        messages.success(
                            request,
                            "Your subscription has been scheduled for cancellation.",
                        )

                logger.info(
                    f"Cancelled subscription for user {request.user.id}: {cancel_type}"
                )

            except Exception as e:
                logger.error(
                    f"Error cancelling subscription for user {request.user.id}: {str(e)}"
                )
                messages.error(
                    request,
                    "Unable to process cancellation. Please try again or contact support.",
                )
        else:
            messages.warning(request, "No active subscription found to cancel.")

        return redirect(user_sub_obj.get_absolute_url())

    # Get cancellation reasons for the form
    cancellation_reasons = [
        ("too_expensive", "Too expensive"),
        ("not_using", "Not using enough"),
        ("missing_features", "Missing features I need"),
        ("found_alternative", "Found a better alternative"),
        ("temporary_pause", "Taking a temporary break"),
        ("other", "Other reason"),
    ]

    context = {
        "subscription": user_sub_obj,
        "cancellation_reasons": cancellation_reasons,
        "has_active_subscription": user_sub_obj.is_active_status,
    }

    return render(request, "subscriptions/user_cancel_view.html", context)


# Create your views here.
def subscription_price_view(request, interval="month"):
    """
    Enhanced pricing page with better filtering and user experience
    """
    # Get featured subscription prices
    qs = SubscriptionPrice.objects.filter(
        featured=True, subscription__active=True
    ).select_related("subscription")

    # Define interval choices
    inv_mo = SubscriptionPrice.IntervalChoices.MONTHLY
    inv_yr = SubscriptionPrice.IntervalChoices.YEARLY

    # Validate interval parameter
    valid_intervals = [inv_mo, inv_yr]
    if interval not in valid_intervals:
        interval = inv_mo

    # Filter by interval
    object_list = qs.filter(interval=interval).order_by("subscription__order", "price")

    # Generate URLs for interval switching
    url_path_name = "pricing_interval"
    mo_url = reverse(url_path_name, kwargs={"interval": inv_mo})
    yr_url = reverse(url_path_name, kwargs={"interval": inv_yr})

    # Calculate savings for yearly plans if available
    yearly_savings = {}
    if interval == inv_yr:
        for price_obj in object_list:
            try:
                monthly_price = SubscriptionPrice.objects.get(
                    subscription=price_obj.subscription, interval=inv_mo, featured=True
                )
                yearly_total = float(monthly_price.price) * 12
                yearly_price = float(price_obj.price)
                savings = yearly_total - yearly_price
                if savings > 0:
                    yearly_savings[price_obj.id] = {
                        "amount": savings,
                        "percentage": round((savings / yearly_total) * 100),
                    }
            except SubscriptionPrice.DoesNotExist:
                continue

    # Check if user has existing subscription
    user_subscription = None
    if request.user.is_authenticated:
        try:
            user_subscription = UserSubscription.objects.get(user=request.user)
        except UserSubscription.DoesNotExist:
            pass

    context = {
        "object_list": object_list,
        "mo_url": mo_url,
        "yr_url": yr_url,
        "active": interval,
        "yearly_savings": yearly_savings,
        "user_subscription": user_subscription,
        "is_yearly": interval == inv_yr,
        "is_monthly": interval == inv_mo,
    }

    return render(request, "subscriptions/pricing.html", context)


@require_http_methods(["GET"])
@login_required
def subscription_status_api(request):
    """
    API endpoint to get current user's subscription status
    """
    try:
        user_sub = UserSubscription.objects.get(user=request.user)
        return JsonResponse(
            {
                "has_subscription": True,
                "plan_name": user_sub.plan_name,
                "status": user_sub.status,
                "is_active": user_sub.is_active_status,
                "current_period_end": (
                    user_sub.current_period_end.isoformat()
                    if user_sub.current_period_end
                    else None
                ),
                "cancel_at_period_end": user_sub.cancel_at_period_end,
            }
        )
    except UserSubscription.DoesNotExist:
        return JsonResponse(
            {
                "has_subscription": False,
                "plan_name": None,
                "status": None,
                "is_active": False,
                "current_period_end": None,
                "cancel_at_period_end": False,
            }
        )
    except Exception as e:
        logger.error(f"Error in subscription status API: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@login_required
def subscription_upgrade_view(request, price_id):
    """
    Handle subscription upgrades/changes
    """
    try:
        new_price = get_object_or_404(
            SubscriptionPrice, id=price_id, subscription__active=True
        )

        user_sub = UserSubscription.objects.get(user=request.user)

        # Check if it's actually a change
        current_price = None
        if user_sub.subscription:
            current_price = SubscriptionPrice.objects.filter(
                subscription=user_sub.subscription, stripe_id__isnull=False
            ).first()

        if current_price and current_price.id == new_price.id:
            messages.info(request, "You're already subscribed to this plan.")
            return redirect("user_subscription")

        # Store upgrade info and redirect to checkout
        request.session["checkout_subscription_price_id"] = price_id
        request.session["checkout_is_upgrade"] = True

        messages.info(request, f"Upgrading to {new_price.display_sub_name}...")
        return redirect("stripe-checkout-start")

    except UserSubscription.DoesNotExist:
        # No existing subscription, treat as new signup
        request.session["checkout_subscription_price_id"] = price_id
        return redirect("stripe-checkout-start")
    except Exception as e:
        logger.error(f"Error in subscription upgrade: {str(e)}")
        messages.error(request, "Unable to process upgrade. Please try again.")
        return redirect("pricing")

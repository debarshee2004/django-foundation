import helpers.billing
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponseBadRequest

from subscriptions.models import SubscriptionPrice, Subscription, UserSubscription

User = get_user_model()

BASE_URL = settings.BASE_URL


# Create your views here.
def product_price_redirect_view(request, price_id=None, *args, **kwargs):
    request.session["checkout_subscription_price_id"] = price_id
    return redirect("stripe-checkout-start")


@login_required
def checkout_redirect_view(request):
    checkout_subscription_price_id = request.session.get(
        "checkout_subscription_price_id"
    )
    try:
        obj = SubscriptionPrice.objects.get(id=checkout_subscription_price_id)
    except:
        obj = None
    if checkout_subscription_price_id is None or obj is None:
        return redirect("pricing")

    try:
        customer_stripe_id = request.user.customer.stripe_id
    except AttributeError:
        messages.error(request, "Customer profile not found. Please contact support.")
        return redirect("pricing")

    if not customer_stripe_id:
        messages.error(request, "Customer profile incomplete. Please contact support.")
        return redirect("pricing")

    success_url_path = reverse("stripe-checkout-end")
    pricing_url_path = reverse("pricing")
    success_url = f"{BASE_URL}{success_url_path}"
    cancel_url = f"{BASE_URL}{pricing_url_path}"
    price_stripe_id = str(obj.stripe_id) if obj.stripe_id else ""

    if not price_stripe_id:
        messages.error(request, "Invalid pricing configuration.")
        return redirect("pricing")

    url = helpers.billing.start_checkout_session(
        customer_stripe_id,
        success_url=success_url,
        cancel_url=cancel_url,
        price_stripe_id=price_stripe_id,
        raw=False,
    )
    return redirect(url)


def checkout_finalize_view(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        return HttpResponseBadRequest("Missing session ID.")

    checkout_data = helpers.billing.get_checkout_customer_plan(session_id)
    if not checkout_data or not isinstance(checkout_data, dict):
        return HttpResponseBadRequest(
            "Unable to retrieve checkout information. Please contact support."
        )

    plan_id = checkout_data.pop("plan_id", None)
    customer_id = checkout_data.pop("customer_id", None)
    sub_stripe_id = checkout_data.pop("sub_stripe_id", None)
    subscription_data = {**checkout_data}

    if not all([plan_id, customer_id, sub_stripe_id]):
        return HttpResponseBadRequest(
            "Incomplete checkout data. Please contact support."
        )

    try:
        sub_obj = Subscription.objects.get(subscriptionprice__stripe_id=plan_id)
    except Subscription.DoesNotExist:
        return HttpResponseBadRequest("Invalid subscription plan.")
    except Exception:
        return HttpResponseBadRequest("Error retrieving subscription plan.")

    try:
        user_obj = User.objects.get(customer__stripe_id=customer_id)
    except User.DoesNotExist:
        return HttpResponseBadRequest("Customer not found.")
    except Exception:
        return HttpResponseBadRequest("Error retrieving customer.")

    _user_sub_exists = False
    updated_sub_options = {
        "subscription": sub_obj,
        "stripe_id": sub_stripe_id,
        "user_cancelled": False,
        **subscription_data,
    }
    try:
        _user_sub_obj = UserSubscription.objects.get(user=user_obj)
        _user_sub_exists = True
    except UserSubscription.DoesNotExist:
        try:
            _user_sub_obj = UserSubscription.objects.create(
                user=user_obj, **updated_sub_options
            )
        except Exception as e:
            return HttpResponseBadRequest(f"Error creating subscription: {str(e)}")
    except Exception:
        return HttpResponseBadRequest("Error accessing user subscription.")

    if _user_sub_exists and _user_sub_obj:
        # cancel old sub
        old_stripe_id = _user_sub_obj.stripe_id
        same_stripe_id = sub_stripe_id == old_stripe_id
        if old_stripe_id is not None and not same_stripe_id:
            try:
                helpers.billing.cancel_subscription(
                    old_stripe_id, reason="Auto ended, new membership", feedback="other"
                )
            except Exception:
                # Log the error but don't fail the process
                pass
        # assign new sub
        try:
            for k, v in updated_sub_options.items():
                setattr(_user_sub_obj, k, v)
            _user_sub_obj.save()
            messages.success(request, "Success! Thank you for joining.")
            return redirect(_user_sub_obj.get_absolute_url())
        except Exception as e:
            return HttpResponseBadRequest(f"Error updating subscription: {str(e)}")

    # If we get here, the subscription was just created
    messages.success(request, "Success! Thank you for joining.")
    context = {"subscription": _user_sub_obj}
    return render(request, "checkout/success.html", context)

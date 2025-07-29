import stripe
from decouple import config
from typing import Literal, Union, Dict, Any

from . import date_utils

DJANGO_DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="", cast=str)
STRIPE_TEST_OVERRIDE = config("STRIPE_TEST_OVERRIDE", default=False, cast=bool)

if (
    isinstance(STRIPE_SECRET_KEY, str)
    and STRIPE_SECRET_KEY
    and "sk_test" in STRIPE_SECRET_KEY
    and not DJANGO_DEBUG
    and not STRIPE_TEST_OVERRIDE
):
    raise ValueError("Invalid stripe key for prod")

stripe.api_key = STRIPE_SECRET_KEY


def serialize_subscription_data(subscription_response: Any) -> Dict[str, Any]:
    status = subscription_response.status
    current_period_start = date_utils.timestamp_as_datetime(
        subscription_response.current_period_start
    )
    current_period_end = date_utils.timestamp_as_datetime(
        subscription_response.current_period_end
    )
    cancel_at_period_end = subscription_response.cancel_at_period_end
    return {
        "current_period_start": current_period_start,
        "current_period_end": current_period_end,
        "status": status,
        "cancel_at_period_end": cancel_at_period_end,
    }


def create_customer(
    name: str = "", email: str = "", metadata: Dict[str, str] = {}, raw: bool = False
):
    response = stripe.Customer.create(
        name=name,
        email=email,
        metadata=metadata,
    )
    if raw:
        return response
    stripe_id = response.id
    return stripe_id


def create_product(name: str = "", metadata: Dict[str, str] = {}, raw: bool = False):
    response = stripe.Product.create(
        name=name,
        metadata=metadata,
    )
    if raw:
        return response
    stripe_id = response.id
    return stripe_id


def create_price(
    currency: str = "usd",
    unit_amount: int = 9999,
    interval: Literal["day", "week", "month", "year"] = "month",
    product: Union[str, None] = None,
    metadata: Dict[str, str] = {},
    raw: bool = False,
):
    if product is None:
        return None

    response = stripe.Price.create(
        currency=currency,
        unit_amount=unit_amount,
        recurring={"interval": interval},
        product=product,
        metadata=metadata,
    )
    if raw:
        return response
    stripe_id = response.id
    return stripe_id


def start_checkout_session(
    customer_id: str,
    success_url: str = "",
    cancel_url: str = "",
    price_stripe_id: str = "",
    raw: bool = True,
):
    if not success_url.endswith("?session_id={CHECKOUT_SESSION_ID}"):
        success_url = f"{success_url}" + "?session_id={CHECKOUT_SESSION_ID}"
    response = stripe.checkout.Session.create(
        customer=customer_id,
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[{"price": price_stripe_id, "quantity": 1}],
        mode="subscription",
    )
    if raw:
        return response
    return response.url


def get_checkout_session(stripe_id: str, raw: bool = True):
    response = stripe.checkout.Session.retrieve(stripe_id)
    if raw:
        return response
    return response.url


def get_subscription(stripe_id: str, raw: bool = True):
    response = stripe.Subscription.retrieve(stripe_id)
    if raw:
        return response
    return serialize_subscription_data(response)


def get_customer_active_subscriptions(customer_stripe_id: str):
    response = stripe.Subscription.list(customer=customer_stripe_id, status="active")
    return response


def cancel_subscription(
    stripe_id: str,
    reason: str = "",
    feedback: Literal[
        "",
        "customer_service",
        "low_quality",
        "missing_features",
        "other",
        "switched_service",
        "too_complex",
        "too_expensive",
        "unused",
    ] = "other",
    cancel_at_period_end: bool = False,
    raw: bool = True,
):
    if cancel_at_period_end:
        response = stripe.Subscription.modify(
            stripe_id,
            cancel_at_period_end=cancel_at_period_end,
            cancellation_details={"comment": reason, "feedback": feedback},
        )
    else:
        response = stripe.Subscription.cancel(
            stripe_id, cancellation_details={"comment": reason, "feedback": feedback}
        )
    if raw:
        return response
    return serialize_subscription_data(response)


def get_checkout_customer_plan(session_id: str):
    checkout_r = get_checkout_session(session_id, raw=True)

    # Handle case where checkout_r might be None or a string
    if not checkout_r or isinstance(checkout_r, str):
        return None

    customer_id = checkout_r.customer
    sub_stripe_id = checkout_r.subscription

    # Ensure sub_stripe_id is a string
    if not isinstance(sub_stripe_id, str):
        # If it's an expandable field, get the ID
        if sub_stripe_id and hasattr(sub_stripe_id, "id"):
            sub_stripe_id = sub_stripe_id.id
        else:
            return None

    sub_r = get_subscription(sub_stripe_id, raw=True)

    # Handle case where sub_r might be None
    if not sub_r:
        return None

    # In newer Stripe API versions, subscription items contain price information
    # instead of the deprecated 'plan' attribute
    subscription_data = serialize_subscription_data(sub_r)

    # Get the plan ID - in newer Stripe API versions, we need to handle this differently
    plan_id = None
    try:
        # Try to access items data safely
        items = getattr(sub_r, "items", None)
        if items and hasattr(items, "data"):
            items_data = getattr(items, "data", [])
            if items_data and len(items_data) > 0:
                first_item = items_data[0]
                price = getattr(first_item, "price", None)
                if price:
                    plan_id = getattr(price, "id", None)
    except (AttributeError, IndexError, TypeError):
        # Fallback: plan_id will remain None
        pass

    data = {
        "customer_id": customer_id,
        "plan_id": plan_id,
        "sub_stripe_id": sub_stripe_id,
        **subscription_data,
    }
    return data

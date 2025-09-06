from django.urls import path
from . import views

app_name = "customers"

urlpatterns = [
    # Dashboard and main pages
    path("dashboard/", views.customer_dashboard, name="dashboard"),
    path("billing/", views.billing_portal, name="billing"),
    path("subscription/", views.subscription_management, name="subscription"),
    path("support/", views.support_center, name="support"),
    # AJAX endpoints
    path("api/sync/", views.sync_customer_data, name="sync_data"),
    path("api/status/", views.customer_api_status, name="api_status"),
    # Account management
    path("delete-account/", views.delete_customer_account, name="delete_account"),
    # Webhooks
    path("webhook/stripe/", views.webhook_stripe, name="webhook_stripe"),
]

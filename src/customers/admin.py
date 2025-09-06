from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Sum
from django.http import HttpResponse
import csv
import logging

from .models import Customer

logger = logging.getLogger("customers")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """
    Enhanced admin interface for Customer management

    Features:
    - Comprehensive customer information display
    - Filtering and searching capabilities
    - Bulk actions for customer management
    - Integration with Stripe data
    - Export functionality
    """

    # List display configuration
    list_display = [
        "display_name",
        "email",
        "subscription_status_badge",
        "stripe_id_display",
        "lifetime_value_display",
        "email_confirmed_status",
        "customer_since",
        "last_stripe_sync_display",
        "user_actions",
    ]

    # List filtering options
    list_filter = [
        "subscription_status",
        "is_active",
        "init_email_confirmed",
        "customer_since",
        "last_stripe_sync",
        ("user__is_active", admin.BooleanFieldListFilter),
        ("user__is_staff", admin.BooleanFieldListFilter),
    ]

    # Search configuration
    search_fields = [
        "user__email",
        "user__username",
        "user__first_name",
        "user__last_name",
        "stripe_id",
        "init_email",
    ]

    # Ordering
    ordering = ["-created_at"]

    # Fields to display in detail view
    fields = [
        "user",
        "stripe_id",
        "subscription_status",
        "is_active",
        "init_email",
        "init_email_confirmed",
        "customer_since",
        "lifetime_value",
        "last_stripe_sync",
        "notes",
    ]

    # Read-only fields
    readonly_fields = [
        "customer_since",
        "created_at",
        "updated_at",
        "last_stripe_sync",
    ]

    # Raw ID fields for performance
    raw_id_fields = ["user"]

    # Pagination
    list_per_page = 50

    # Enable date hierarchy
    date_hierarchy = "created_at"

    # Custom methods for display
    def display_name(self, obj):
        """Display customer's full name or username"""
        return obj.display_name

    display_name.short_description = "Customer Name"
    display_name.admin_order_field = "user__first_name"

    def email(self, obj):
        """Display customer email with link to user admin"""
        user_admin_url = reverse("admin:auth_customuser_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', user_admin_url, obj.user.email)

    email.short_description = "Email"
    email.admin_order_field = "user__email"

    def subscription_status_badge(self, obj):
        """Display subscription status with color coding"""
        status_colors = {
            "none": "gray",
            "trial": "blue",
            "active": "green",
            "past_due": "orange",
            "canceled": "red",
            "paused": "yellow",
        }
        color = status_colors.get(obj.subscription_status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_subscription_status_display(),
        )

    subscription_status_badge.short_description = "Subscription"
    subscription_status_badge.admin_order_field = "subscription_status"

    def stripe_id_display(self, obj):
        """Display Stripe ID with link to Stripe dashboard"""
        if obj.stripe_id:
            stripe_url = f"https://dashboard.stripe.com/customers/{obj.stripe_id}"
            return format_html(
                '<a href="{}" target="_blank">{}</a>', stripe_url, obj.stripe_id
            )
        return "-"

    stripe_id_display.short_description = "Stripe ID"
    stripe_id_display.admin_order_field = "stripe_id"

    def lifetime_value_display(self, obj):
        """Display lifetime value with currency formatting"""
        if obj.lifetime_value > 0:
            return f"${obj.lifetime_value:,.2f}"
        return "-"

    lifetime_value_display.short_description = "LTV"
    lifetime_value_display.admin_order_field = "lifetime_value"

    def email_confirmed_status(self, obj):
        """Display email confirmation status with icon"""
        if obj.init_email_confirmed:
            return format_html('<span style="color: green;">✓ Confirmed</span>')
        return format_html('<span style="color: red;">✗ Pending</span>')

    email_confirmed_status.short_description = "Email Status"
    email_confirmed_status.admin_order_field = "init_email_confirmed"

    def last_stripe_sync_display(self, obj):
        """Display last Stripe sync time"""
        if obj.last_stripe_sync:
            time_diff = timezone.now() - obj.last_stripe_sync
            if time_diff.days > 7:
                return format_html(
                    '<span style="color: orange;">{}</span>',
                    obj.last_stripe_sync.strftime("%m/%d/%Y"),
                )
            return obj.last_stripe_sync.strftime("%m/%d/%Y")
        return "-"

    last_stripe_sync_display.short_description = "Last Sync"
    last_stripe_sync_display.admin_order_field = "last_stripe_sync"

    def user_actions(self, obj):
        """Display action buttons for the customer"""
        actions = []

        # Sync with Stripe button
        if obj.stripe_id:
            actions.append(
                f'<a href="javascript:syncCustomer(\'{obj.id}\')" style="color: blue;">Sync</a>'
            )

        # View profile button
        if hasattr(obj.user, "profile"):
            profile_url = reverse(
                "admin:auth_userprofile_change", args=[obj.user.profile.id]
            )
            actions.append(f'<a href="{profile_url}" style="color: green;">Profile</a>')

        return format_html(" | ".join(actions)) if actions else "-"

    user_actions.short_description = "Actions"

    # Custom actions
    actions = [
        "sync_selected_customers",
        "export_customers_csv",
        "mark_as_active",
        "mark_as_inactive",
    ]

    def sync_selected_customers(self, request, queryset):
        """Sync selected customers with Stripe"""
        synced_count = 0
        for customer in queryset.filter(stripe_id__isnull=False):
            try:
                customer.sync_with_stripe()
                synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync customer {customer.id}: {str(e)}")

        self.message_user(
            request, f"Successfully synced {synced_count} customers with Stripe."
        )

    sync_selected_customers.short_description = "Sync selected customers with Stripe"

    def export_customers_csv(self, request, queryset):
        """Export selected customers to CSV"""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="customers.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Customer Name",
                "Email",
                "Username",
                "Subscription Status",
                "Stripe ID",
                "Lifetime Value",
                "Customer Since",
                "Email Confirmed",
            ]
        )

        for customer in queryset:
            writer.writerow(
                [
                    customer.display_name,
                    customer.user.email,
                    customer.user.username,
                    customer.subscription_status,
                    customer.stripe_id or "",
                    customer.lifetime_value,
                    customer.customer_since.strftime("%Y-%m-%d"),
                    "Yes" if customer.init_email_confirmed else "No",
                ]
            )

        return response

    export_customers_csv.short_description = "Export selected customers to CSV"

    def mark_as_active(self, request, queryset):
        """Mark selected customers as active"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request, f"Successfully marked {updated} customers as active."
        )

    mark_as_active.short_description = "Mark selected customers as active"

    def mark_as_inactive(self, request, queryset):
        """Mark selected customers as inactive"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request, f"Successfully marked {updated} customers as inactive."
        )

    mark_as_inactive.short_description = "Mark selected customers as inactive"

    # Custom admin templates
    change_list_template = "admin/customers/customer/change_list.html"

    def changelist_view(self, request, extra_context=None):
        """Add custom context to the changelist view"""
        extra_context = extra_context or {}

        # Add aggregate statistics
        total_customers = Customer.objects.count()
        active_subscriptions = Customer.objects.filter(
            subscription_status="active"
        ).count()
        total_revenue = (
            Customer.objects.aggregate(Sum("lifetime_value"))["lifetime_value__sum"]
            or 0
        )

        extra_context.update(
            {
                "total_customers": total_customers,
                "active_subscriptions": active_subscriptions,
                "total_revenue": total_revenue,
                "conversion_rate": (
                    (active_subscriptions / total_customers * 100)
                    if total_customers > 0
                    else 0
                ),
            }
        )

        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related("user")

    class Media:
        """Include custom JavaScript for admin interface"""

        js = ("admin/js/customer_admin.js",)


class CustomerInline(admin.StackedInline):
    """
    Inline admin for Customer model to show in User admin
    """

    model = Customer
    extra = 0
    fields = [
        "stripe_id",
        "subscription_status",
        "is_active",
        "init_email_confirmed",
        "lifetime_value",
        "notes",
    ]
    readonly_fields = ["stripe_id", "lifetime_value"]


class CustomerAdminSite(admin.AdminSite):
    """
    Custom admin site with customer-specific dashboard
    """

    site_header = "Customer Management"
    site_title = "Customer Admin"
    index_title = "Customer Dashboard"

    def index(self, request, extra_context=None):
        """Custom admin index with customer statistics"""
        extra_context = extra_context or {}

        # Customer statistics
        customer_stats = {
            "total_customers": Customer.objects.count(),
            "active_customers": Customer.objects.filter(is_active=True).count(),
            "customers_with_stripe": Customer.objects.filter(
                stripe_id__isnull=False
            ).count(),
            "trial_customers": Customer.objects.filter(
                subscription_status="trial"
            ).count(),
            "active_subscriptions": Customer.objects.filter(
                subscription_status="active"
            ).count(),
            "canceled_subscriptions": Customer.objects.filter(
                subscription_status="canceled"
            ).count(),
        }

        # Revenue statistics
        revenue_stats = Customer.objects.aggregate(
            total_revenue=Sum("lifetime_value"),
            avg_revenue=(
                Sum("lifetime_value") / Count("id")
                if Customer.objects.count() > 0
                else 0
            ),
        )

        extra_context.update(
            {
                "customer_stats": customer_stats,
                "revenue_stats": revenue_stats,
            }
        )

        return super().index(request, extra_context)


# Register with default admin site
# admin.site.register(Customer, CustomerAdmin)

# Create custom admin site if needed
# customer_admin_site = CustomerAdminSite(name='customer_admin')

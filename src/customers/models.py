import helpers.billing
from django.conf import settings
from django.db import models
from django.utils import timezone
import logging

from allauth.account.signals import (
    user_signed_up as allauth_user_signed_up,
    email_confirmed as allauth_email_confirmed,
)

# Initialize logger for customer operations
logger = logging.getLogger("customers")

User = settings.AUTH_USER_MODEL


class CustomerManager(models.Manager):
    """
    Custom manager for Customer model with enhanced business logic
    """

    def create_for_user(self, user, **extra_fields):
        """
        Create a customer instance for a given user

        Args:
            user: The User instance to create a customer for
            **extra_fields: Additional fields for the customer

        Returns:
            Customer: The created customer instance
        """
        customer = self.create(
            user=user,
            init_email=user.email,
            init_email_confirmed=getattr(user, "email_verified", False),
            **extra_fields,
        )

        logger.info(f"Customer created for user: {user.email} (ID: {customer.id})")
        return customer

    def get_by_user_email(self, email):
        """
        Get customer by user email

        Args:
            email (str): User email address

        Returns:
            Customer: Customer instance or None
        """
        try:
            return self.select_related("user").get(user__email=email)
        except self.model.DoesNotExist:
            return None

    def active_customers(self):
        """
        Get all customers with active Stripe accounts

        Returns:
            QuerySet: Active customers with Stripe IDs
        """
        return self.filter(
            stripe_id__isnull=False, user__is_active=True
        ).select_related("user")


class Customer(models.Model):
    """
    Enhanced Customer model for SaaS business logic

    This model handles the relationship between users and Stripe customers,
    manages subscription states, and tracks customer lifecycle events.
    """

    # Relationships
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="customer_profile"
    )

    # Stripe Integration
    stripe_id = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        unique=True,
        help_text="Stripe customer ID",
    )

    # Email Management
    init_email = models.EmailField(
        blank=True, null=True, help_text="Initial email used for customer creation"
    )
    init_email_confirmed = models.BooleanField(
        default=False, help_text="Whether the initial email has been confirmed"
    )

    # Customer Status and Metadata
    is_active = models.BooleanField(
        default=True, help_text="Whether the customer account is active"
    )

    customer_since = models.DateTimeField(
        default=timezone.now, help_text="When the customer account was created"
    )

    last_stripe_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time customer data was synced with Stripe",
    )

    # Business Intelligence Fields
    lifetime_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Total revenue from this customer",
    )

    subscription_status = models.CharField(
        max_length=50,
        default="none",
        choices=[
            ("none", "No Subscription"),
            ("trial", "Free Trial"),
            ("active", "Active Subscription"),
            ("past_due", "Past Due"),
            ("canceled", "Canceled"),
            ("paused", "Paused"),
        ],
        help_text="Current subscription status",
    )

    # Metadata
    notes = models.TextField(blank=True, help_text="Internal notes about the customer")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomerManager()

    class Meta:
        db_table = "customers_customer"
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        indexes = [
            models.Index(fields=["stripe_id"]),
            models.Index(fields=["subscription_status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.user.email})"

    def save(self, *args, **kwargs):
        """
        Enhanced save method with Stripe customer creation and business logic
        """
        # Create Stripe customer if conditions are met
        if not self.stripe_id and self.should_create_stripe_customer():
            try:
                self.create_stripe_customer()
            except Exception as e:
                logger.error(
                    f"Failed to create Stripe customer for {self.user.email}: {str(e)}"
                )
                # Don't prevent saving if Stripe creation fails

        # Update sync timestamp
        if self.stripe_id and not self.last_stripe_sync:
            self.last_stripe_sync = timezone.now()

        super().save(*args, **kwargs)

    def should_create_stripe_customer(self):
        """
        Determine if a Stripe customer should be created

        Returns:
            bool: True if Stripe customer should be created
        """
        return (
            self.init_email_confirmed
            and self.init_email
            and self.init_email.strip() != ""
            and self.user.is_active
        )

    def create_stripe_customer(self):
        """
        Create a Stripe customer for this customer instance

        Returns:
            str: Stripe customer ID
        """
        if self.stripe_id:
            logger.warning(f"Stripe customer already exists for {self.user.email}")
            return self.stripe_id

        try:
            # Prepare customer metadata
            metadata = {
                "user_id": str(self.user.id),
                "username": self.user.username,
                "customer_id": str(self.id),
                "created_via": "django_auth_system",
                "registration_date": self.created_at.isoformat(),
            }

            # Add profile information if available
            if hasattr(self.user, "profile"):
                profile = self.user.profile
                metadata.update(
                    {
                        "country": profile.country or "",
                        "timezone": profile.timezone or "UTC",
                    }
                )

            # Create Stripe customer
            stripe_id = helpers.billing.create_customer(
                email=self.init_email,
                name=self.user.get_full_name() or self.user.username,
                metadata=metadata,
                raw=False,
            )

            if stripe_id:
                self.stripe_id = stripe_id
                self.last_stripe_sync = timezone.now()
                logger.info(
                    f"Stripe customer created: {stripe_id} for user {self.user.email}"
                )
                return stripe_id
            else:
                raise ValueError("Stripe customer creation returned empty ID")

        except Exception as e:
            logger.error(
                f"Failed to create Stripe customer for {self.user.email}: {str(e)}"
            )
            raise

    def sync_with_stripe(self):
        """
        Sync customer data with Stripe

        Returns:
            dict: Stripe customer data
        """
        if not self.stripe_id:
            raise ValueError("No Stripe customer ID available for sync")

        try:
            # This would call your Stripe sync function
            stripe_data = helpers.billing.get_customer(self.stripe_id)

            # Update local data based on Stripe data
            if stripe_data:
                self.last_stripe_sync = timezone.now()
                self.save(update_fields=["last_stripe_sync"])
                logger.info(f"Customer synced with Stripe: {self.stripe_id}")

            return stripe_data

        except Exception as e:
            logger.error(
                f"Failed to sync customer {self.stripe_id} with Stripe: {str(e)}"
            )
            raise

    def update_subscription_status(self, status):
        """
        Update the subscription status and trigger related actions

        Args:
            status (str): New subscription status
        """
        old_status = self.subscription_status
        self.subscription_status = status
        self.save(update_fields=["subscription_status", "updated_at"])

        logger.info(
            f"Subscription status updated for {self.user.email}: {old_status} -> {status}"
        )

        # Trigger status-specific actions
        self._handle_subscription_status_change(old_status, status)

    def _handle_subscription_status_change(self, old_status, new_status):
        """
        Handle subscription status change events

        Args:
            old_status (str): Previous subscription status
            new_status (str): New subscription status
        """
        # Send notifications, update permissions, etc.
        if new_status == "active" and old_status != "active":
            # Customer became active - grant access
            self._grant_subscription_access()
        elif new_status in ["canceled", "past_due"] and old_status == "active":
            # Customer lost access - revoke permissions
            self._revoke_subscription_access()

    def _grant_subscription_access(self):
        """Grant subscription-based access to the user"""
        # Add user to subscription groups, update permissions, etc.
        logger.info(f"Granting subscription access to {self.user.email}")
        # Implementation depends on your access control system

    def _revoke_subscription_access(self):
        """Revoke subscription-based access from the user"""
        # Remove user from subscription groups, update permissions, etc.
        logger.info(f"Revoking subscription access from {self.user.email}")
        # Implementation depends on your access control system

    @property
    def has_active_subscription(self):
        """Check if customer has an active subscription"""
        return self.subscription_status in ["trial", "active"]

    @property
    def display_name(self):
        """Get display name for the customer"""
        return self.user.get_full_name() or self.user.username

    @property
    def email(self):
        """Get customer email"""
        return self.user.email


def allauth_user_signed_up_handler(request, user, *args, **kwargs):
    """
    Handle user signup to create customer profile

    This signal is triggered when a user signs up through allauth.
    We create a customer profile but don't create the Stripe customer
    until email is confirmed.

    Args:
        request: The HTTP request
        user: The newly created user instance
    """
    try:
        email = user.email

        # Create customer profile
        customer = Customer.objects.create_for_user(
            user=user,
            init_email=email,
            init_email_confirmed=False,
            subscription_status="none",
        )

        logger.info(f"Customer profile created for new user: {email}")

        # Send welcome email or perform other onboarding tasks
        # send_welcome_email(user)

    except Exception as e:
        logger.error(f"Failed to create customer for user {user.email}: {str(e)}")
        # Don't prevent user creation if customer creation fails


def allauth_email_confirmed_handler(request, email_address, *args, **kwargs):
    """
    Handle email confirmation to activate customer and create Stripe customer

    This signal is triggered when a user confirms their email address.
    We update the customer profile and create the Stripe customer.

    Args:
        request: The HTTP request
        email_address: The confirmed email address
    """
    try:
        # Find customers with this email that haven't been confirmed
        customers = Customer.objects.filter(
            init_email=email_address,
            init_email_confirmed=False,
        ).select_related("user")

        for customer in customers:
            # Update email confirmation status
            customer.init_email_confirmed = True

            # Update user's email verification status if using custom user model
            if hasattr(customer.user, "email_verified"):
                customer.user.email_verified = True
                customer.user.save(update_fields=["email_verified"])

            # Save customer (this will trigger Stripe customer creation)
            customer.save()

            logger.info(
                f"Email confirmed and Stripe customer created for: {email_address}"
            )

            # Send confirmation success email or perform other post-confirmation tasks
            # send_email_confirmed_notification(customer.user)

    except Exception as e:
        logger.error(
            f"Failed to handle email confirmation for {email_address}: {str(e)}"
        )


def user_profile_updated_handler(sender, instance, created, **kwargs):
    """
    Handle user profile updates to sync with customer data

    This signal is triggered when a UserProfile is updated.
    We sync relevant data with the customer profile and Stripe.

    Args:
        sender: The UserProfile model class
        instance: The UserProfile instance
        created: Whether this is a new instance
    """
    if not created:  # Only handle updates, not creation
        try:
            # Get or create customer profile
            customer, customer_created = Customer.objects.get_or_create(
                user=instance.user,
                defaults={
                    "init_email": instance.user.email,
                    "init_email_confirmed": getattr(
                        instance.user, "email_verified", False
                    ),
                },
            )

            # Sync customer data with Stripe if customer exists
            if customer.stripe_id:
                # Update Stripe customer with new profile data
                try:
                    metadata = {
                        "country": instance.country or "",
                        "timezone": instance.timezone or "UTC",
                        "phone": instance.phone_number or "",
                        "bio": (
                            instance.bio[:100] if instance.bio else ""
                        ),  # Limit bio length
                    }

                    # This would call your Stripe update function
                    # helpers.billing.update_customer(customer.stripe_id, metadata=metadata)

                    customer.last_stripe_sync = timezone.now()
                    customer.save(update_fields=["last_stripe_sync"])

                    logger.info(
                        f"Customer profile synced with Stripe: {customer.user.email}"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to sync customer profile with Stripe: {str(e)}"
                    )

        except Exception as e:
            logger.error(
                f"Failed to handle profile update for user {instance.user.email}: {str(e)}"
            )


# Connect signal handlers
allauth_user_signed_up.connect(allauth_user_signed_up_handler)
allauth_email_confirmed.connect(allauth_email_confirmed_handler)

# Connect to UserProfile updates if the model exists
try:
    from auth.models import UserProfile
    from django.db.models.signals import post_save

    post_save.connect(
        user_profile_updated_handler,
        sender=UserProfile,
        dispatch_uid="customer_profile_sync",
    )
except ImportError:
    logger.warning("UserProfile model not found - profile sync signals not connected")


def create_customer_from_checkout(user, stripe_customer_id=None):
    """
    Create or update customer from checkout process

    Args:
        user: User instance
        stripe_customer_id: Optional existing Stripe customer ID

    Returns:
        Customer: The customer instance
    """
    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            "init_email": user.email,
            "init_email_confirmed": True,  # Assume confirmed if they can checkout
            "stripe_id": stripe_customer_id,
            "subscription_status": "trial" if not stripe_customer_id else "none",
        },
    )

    if not created and stripe_customer_id and not customer.stripe_id:
        customer.stripe_id = stripe_customer_id
        customer.last_stripe_sync = timezone.now()
        customer.save()

    logger.info(
        f"Customer {'created' if created else 'updated'} from checkout: {user.email}"
    )
    return customer


def handle_subscription_webhook(stripe_event):
    """
    Handle Stripe webhook events for subscription changes

    Args:
        stripe_event: Stripe event object

    Returns:
        bool: True if handled successfully
    """
    try:
        event_type = stripe_event.get("type")
        data = stripe_event.get("data", {}).get("object", {})

        if event_type.startswith("customer.subscription."):
            # Handle subscription events
            customer_id = data.get("customer")
            status = data.get("status")

            if customer_id and status:
                try:
                    customer = Customer.objects.get(stripe_id=customer_id)
                    customer.update_subscription_status(status)
                    return True
                except Customer.DoesNotExist:
                    logger.warning(f"Customer not found for Stripe ID: {customer_id}")

        elif event_type.startswith("invoice."):
            # Handle invoice events for lifetime value tracking
            customer_id = data.get("customer")
            amount_paid = data.get("amount_paid", 0) / 100  # Convert from cents

            if customer_id and amount_paid > 0:
                try:
                    customer = Customer.objects.get(stripe_id=customer_id)
                    customer.lifetime_value += amount_paid
                    customer.save(update_fields=["lifetime_value"])
                    logger.info(
                        f"Updated lifetime value for {customer.user.email}: +${amount_paid}"
                    )
                    return True
                except Customer.DoesNotExist:
                    logger.warning(f"Customer not found for Stripe ID: {customer_id}")

        return False

    except Exception as e:
        logger.error(f"Failed to handle Stripe webhook: {str(e)}")
        return False

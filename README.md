# Django SaaS Foundation

A comprehensive, production-ready Django foundation for building Software-as-a-Service (SaaS) applications. This project provides a complete starting point with user authentication, subscription management, payment processing, customer management, and modern responsive UI components.

## 🎯 Project Overview

This Django SaaS Foundation is designed to accelerate the development of subscription-based web applications. Rather than building common SaaS features from scratch, this foundation provides a robust, scalable architecture that handles the complex business logic of user management, billing, subscriptions, and customer relationships.

### Key Features

- **🔐 Complete Authentication System** - Django Allauth integration with social login support
- **💳 Stripe Payment Integration** - Full subscription lifecycle management
- **👥 Customer Relationship Management** - Advanced customer profiles and lifecycle tracking
- **📊 Subscription Management** - Flexible subscription plans, pricing tiers, and billing cycles
- **🚀 Modern Landing Pages** - Responsive, conversion-optimized marketing pages
- **📈 Analytics & Tracking** - Visit tracking and customer behavior analytics
- **🎨 Modern UI Components** - TailwindCSS-powered responsive design
- **🔧 Admin Interface** - Enhanced Django admin for business management
- **📧 Email Integration** - User notifications and lifecycle emails
- **🌙 Dark Mode Support** - Complete dark/light theme switching

## 🏗️ Project Architecture

### Core Django Applications

#### 1. **Authentication (`auth/`)**

Extends Django's built-in authentication with enhanced user management:

```python
# Custom User Profile with extended fields
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', blank=True)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=30, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
```

**Features:**

- Django Allauth integration for social authentication (Google, GitHub)
- Custom user profiles with extended metadata
- Email verification and password reset flows
- User permission and group management

#### 2. **Customer Management (`customers/`)**

Sophisticated customer relationship management with Stripe integration:

```python
class Customer(models.Model):
    """Enhanced Customer model for SaaS business logic"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    stripe_id = models.CharField(max_length=120, unique=True)
    subscription_status = models.CharField(max_length=50, default="none")
    lifetime_value = models.DecimalField(max_digits=10, decimal_places=2)
    last_stripe_sync = models.DateTimeField(null=True, blank=True)
```

**Business Logic:**

- **Automatic Customer Creation**: Creates Stripe customers when users sign up
- **Subscription Status Tracking**: Real-time sync with Stripe subscription states
- **Lifetime Value Calculation**: Tracks total revenue per customer
- **Permission Management**: Grants/revokes access based on subscription status
- **Webhook Handling**: Processes Stripe events for real-time updates

**Key Methods:**

- `create_stripe_customer()`: Creates corresponding Stripe customer
- `sync_with_stripe()`: Syncs local data with Stripe
- `update_subscription_status()`: Handles subscription state changes
- `has_active_subscription`: Property for access control

#### 3. **Subscription Management (`subscriptions/`)**

Comprehensive subscription and pricing management:

```python
class Subscription(models.Model):
    """Subscription Plan = Stripe Product"""
    name = models.CharField(max_length=120)
    stripe_id = models.CharField(max_length=120)
    groups = models.ManyToManyField(Group)
    permissions = models.ManyToManyField(Permission)
    features = models.TextField()  # Newline-separated features

class SubscriptionPrice(models.Model):
    """Subscription Price = Stripe Price"""
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL)
    stripe_id = models.CharField(max_length=120)
    interval = models.CharField(max_length=120)  # monthly, yearly
    price = models.DecimalField(max_digits=10, decimal_places=2)

class UserSubscription(models.Model):
    """User's active subscription"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL)
    stripe_id = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=SubscriptionStatus.choices)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
```

**Advanced Features:**

- **Multi-tier Pricing**: Support for multiple subscription plans
- **Flexible Billing Cycles**: Monthly, yearly, or custom intervals
- **Feature Gating**: Permission-based feature access
- **Subscription Lifecycle**: Trial, active, past_due, canceled states
- **Billing Cycle Management**: Prorated upgrades/downgrades
- **Cancellation Handling**: End-of-period vs immediate cancellation

#### 4. **Checkout & Payment Processing (`checkouts/`)**

Secure, robust payment processing with Stripe Checkout:

```python
def checkout_redirect_view(request):
    """Create Stripe Checkout session with enhanced error handling"""
    try:
        customer = get_customer_or_create(request.user)
        price_id = request.session.get('checkout_subscription_price_id')

        checkout_session = helpers.billing.create_checkout_session(
            customer_id=customer.stripe_id,
            price_id=price_id,
            success_url=request.build_absolute_uri('/checkout/success/'),
            cancel_url=request.build_absolute_uri('/pricing/')
        )

        return redirect(checkout_session.url)
    except CheckoutError as e:
        messages.error(request, str(e))
        return redirect('pricing')
```

**Payment Flow:**

1. **Price Selection**: User selects subscription plan
2. **Checkout Session**: Creates Stripe Checkout session
3. **Payment Processing**: Stripe handles payment securely
4. **Webhook Processing**: Real-time subscription activation
5. **User Notification**: Success confirmation and access granting

**Error Handling:**

- Payment failures with user-friendly messages
- Duplicate subscription prevention
- Session timeout handling
- Webhook verification and replay protection

#### 5. **Landing Pages (`landing/`)**

Modern, conversion-optimized marketing pages:

**Components:**

- **Hero Section**: Compelling value proposition with animated backgrounds
- **Features Grid**: Detailed feature explanations with icons and benefits
- **Social Proof**: Customer testimonials and usage statistics
- **Pricing Display**: Clear pricing tiers with feature comparisons
- **Call-to-Action**: Strategic CTAs throughout the funnel

**Technical Implementation:**

```html
<!-- Modern gradient hero with animations -->
<section
  class="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50"
>
  <div class="animated-background">
    <!-- Floating geometric shapes -->
  </div>
  <div class="hero-content">
    <h1
      class="text-6xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent"
    >
      Build Your SaaS Empire
    </h1>
  </div>
</section>
```

#### 6. **Analytics & Tracking (`visits/`)**

Comprehensive user behavior tracking:

```python
class PageVisit(models.Model):
    """Track page visits for analytics"""
    path = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
```

**Analytics Features:**

- Page view tracking with user attribution
- Conversion funnel analysis
- Customer journey mapping
- Real-time dashboard metrics
- Geographic and demographic insights

#### 7. **Helper Utilities (`helpers/`)**

Reusable business logic and integrations:

```python
# Stripe integration helpers
def create_checkout_session(customer_id, price_id, success_url, cancel_url):
    """Create Stripe Checkout session with proper error handling"""

def serialize_subscription_data(subscription_response):
    """Convert Stripe subscription to Django model data"""

def handle_webhook_event(event):
    """Process Stripe webhook events securely"""

# Date utilities
def timestamp_as_datetime(timestamp):
    """Convert Unix timestamp to Django datetime"""

# Billing calculations
def calculate_prorated_amount(old_price, new_price, days_remaining):
    """Calculate prorated amounts for plan changes"""
```

#### 8. **Dashboard (`dashboard/`)**

User dashboard with subscription management:

**Features:**

- Subscription status overview
- Usage metrics and analytics
- Billing history and invoices
- Account settings and preferences
- Feature usage tracking

## 🔧 Technical Implementation Details

### Database Schema Design

The application uses a sophisticated relational database schema optimized for SaaS operations:

```sql
-- Core relationships
Users (Django Auth) -> Customer (1:1) -> UserSubscription (1:1)
Subscription (Plan) -> SubscriptionPrice (1:Many)
Customer -> Stripe Customer ID (External)
UserSubscription -> Stripe Subscription ID (External)

-- Indexing strategy
CREATE INDEX idx_customer_stripe_id ON customers_customer(stripe_id);
CREATE INDEX idx_subscription_status ON customers_customer(subscription_status);
CREATE INDEX idx_visit_timestamp ON visits_pagevisit(timestamp);
```

### Stripe Integration Architecture

The application implements a robust Stripe integration with the following patterns:

#### 1. **Dual Data Storage**

- Local Django models for fast queries and business logic
- Stripe as the source of truth for billing data
- Regular synchronization to maintain consistency

#### 2. **Webhook Processing**

```python
@csrf_exempt
def stripe_webhook(request):
    """Process Stripe webhooks securely"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    # Process event based on type
    if event['type'] == 'customer.subscription.updated':
        handle_subscription_updated(event['data']['object'])
    elif event['type'] == 'invoice.payment_succeeded':
        handle_payment_succeeded(event['data']['object'])
```

#### 3. **Error Handling and Retry Logic**

- Exponential backoff for failed API calls
- Idempotency keys for safe retries
- Comprehensive logging for debugging
- Graceful degradation when Stripe is unavailable

### Frontend Architecture

#### 1. **TailwindCSS Design System**

```css
/* Custom design tokens */
:root {
  --primary-blue: #3b82f6;
  --primary-purple: #8b5cf6;
  --success-green: #10b981;
  --gradient-primary: linear-gradient(
    135deg,
    var(--primary-blue),
    var(--primary-purple)
  );
}

/* Component classes */
.btn-primary {
  @apply px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-xl shadow-xl hover:shadow-2xl transform hover:-translate-y-1 transition-all duration-300;
}
```

#### 2. **Responsive Component System**

- Mobile-first responsive design
- Progressive enhancement for advanced features
- Accessibility compliance (WCAG 2.1)
- Cross-browser compatibility

#### 3. **Interactive Elements**

```javascript
// Modern checkout flow
function initializeCheckout(priceId) {
  fetch("/checkout/create-session/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({ price_id: priceId }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    });
}
```

### Security Implementation

#### 1. **Authentication Security**

- CSRF protection on all forms
- Secure session management
- Password strength requirements
- Rate limiting on login attempts

#### 2. **Payment Security**

- PCI DSS compliance through Stripe
- Webhook signature verification
- Secure API key management
- Encrypted data transmission

#### 3. **Access Control**

```python
def subscription_required(view_func):
    """Decorator to require active subscription"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('auth:login')

        customer = getattr(request.user, 'customer_profile', None)
        if not customer or not customer.has_active_subscription:
            messages.warning(request, 'This feature requires an active subscription.')
            return redirect('pricing')

        return view_func(request, *args, **kwargs)
    return wrapper
```

## 🚀 Scalability & Performance

### Database Optimization

- Strategic indexing on frequently queried fields
- Query optimization with select_related and prefetch_related
- Database connection pooling
- Read replicas for analytics queries

### Caching Strategy

```python
# Redis caching for expensive operations
@cache.cache_result(timeout=300)
def get_customer_analytics(customer_id):
    """Cache customer analytics for 5 minutes"""
    return calculate_customer_metrics(customer_id)

# Template fragment caching
{% load cache %}
{% cache 500 pricing_table request.user.id %}
  <!-- Expensive pricing template -->
{% endcache %}
```

### API Performance

- Pagination for large datasets
- Field selection for minimal data transfer
- Compression for API responses
- CDN integration for static assets

## 🔌 Django REST Framework Integration

While the current implementation focuses on server-side rendering, the architecture is designed for easy API expansion:

### Proposed API Endpoints

#### 1. **Authentication API**

```python
# REST API for mobile/SPA integration
class UserRegistrationAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user_id': user.id,
                'email': user.email
            })
        return Response(serializer.errors, status=400)
```

#### 2. **Subscription API**

```python
class SubscriptionViewSet(ModelViewSet):
    """RESTful subscription management"""
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Subscription.objects.filter(active=True)

    @action(detail=True, methods=['post'])
    def subscribe(self, request, pk=None):
        """Subscribe user to a plan"""
        subscription = self.get_object()
        # Create Stripe checkout session
        # Return checkout URL
```

#### 3. **Customer API**

```python
class CustomerViewSet(ModelViewSet):
    """Customer management API"""
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def get_object(self):
        return self.request.user.customer_profile

    @action(detail=False)
    def billing_history(self, request):
        """Get customer billing history"""
        # Return paginated billing history
```

### API Enhancement Roadmap

#### Phase 1: Core APIs

- User authentication and profile management
- Subscription plan listing and selection
- Basic customer information endpoints

#### Phase 2: Advanced Features

- Webhook endpoint for real-time updates
- Analytics and reporting APIs
- Admin APIs for business management

#### Phase 3: Mobile & Third-party Integration

- OAuth2 integration for third-party apps
- Mobile-optimized endpoints
- Rate limiting and API key management

### Serializer Examples

```python
class SubscriptionSerializer(serializers.ModelSerializer):
    """Subscription plan serializer with computed fields"""
    features_list = serializers.SerializerMethodField()
    price_monthly = serializers.SerializerMethodField()
    price_yearly = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = ['id', 'name', 'subtitle', 'features_list',
                 'price_monthly', 'price_yearly', 'featured']

    def get_features_list(self, obj):
        return obj.get_features_as_list()

    def get_price_monthly(self, obj):
        price = obj.subscriptionprice_set.filter(interval='month').first()
        return str(price.price) if price else None

class CustomerAnalyticsSerializer(serializers.Serializer):
    """Customer analytics data"""
    total_visits = serializers.IntegerField()
    subscription_status = serializers.CharField()
    lifetime_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    current_plan = serializers.CharField()
    subscription_start_date = serializers.DateTimeField()
```

## 🛠️ Local Development Setup

### Prerequisites

- Python 3.12 or higher
- PostgreSQL (optional, SQLite for development)
- Redis (optional, for caching)
- Stripe account for payment testing

### Step-by-Step Setup with UV

#### 1. **Clone and Initialize Project**

```bash
# Clone the repository
git clone <repository-url>
cd django-foundation

# Initialize UV environment
uv init --app
```

#### 2. **Install Dependencies**

```bash
# Install all project dependencies
uv add django>=5.2.4
uv add django-allauth[socialaccount]>=65.10.0
uv add stripe>=12.3.0
uv add python-decouple>=3.8
uv add psycopg[binary]>=3.2.9
uv add django-widget-tweaks>=1.5.0
uv add whitenoise>=6.9.0
uv add gunicorn>=23.0.0
uv add requests>=2.32.4
uv add dj-database-url>=3.0.1
uv add django-allauth-ui>=1.8.1

# Or install from pyproject.toml
uv sync
```

#### 3. **Environment Configuration**

Create a `.env` file in the project root:

```bash
# Django settings
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database (optional - uses SQLite by default)
DATABASE_URL=postgresql://user:password@localhost:5432/django_saas

# Email configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Stripe configuration
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Admin user
ADMIN_USER_NAME=Admin User
ADMIN_USER_EMAIL=admin@example.com
```

#### 4. **Database Setup**

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # macOS/Linux

# Navigate to Django project
cd src

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load sample data (optional)
python manage.py loaddata fixtures/sample_data.json
```

#### 5. **Stripe Configuration**

```bash
# Install Stripe CLI for webhook testing
# Download from https://stripe.com/docs/stripe-cli

# Login to Stripe
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/checkout/stripe-webhook/
```

#### 6. **Run Development Server**

```bash
# Start Django development server
python manage.py runserver

# In another terminal, start Stripe webhook forwarding
stripe listen --forward-to localhost:8000/checkout/stripe-webhook/
```

#### 7. **Access the Application**

- **Main Site**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **Landing Page**: http://localhost:8000/
- **Pricing**: http://localhost:8000/pricing/
- **Dashboard**: http://localhost:8000/dashboard/ (requires login)

### Development Workflow

#### 1. **Creating Subscription Plans**

```bash
# Access Django admin
http://localhost:8000/admin

# Create subscription plans:
1. Go to Subscriptions > Subscriptions
2. Add new subscription (creates Stripe product automatically)
3. Add subscription prices for different billing cycles
4. Set features and permissions
```

#### 2. **Testing Payment Flow**

```bash
# Use Stripe test cards:
# Success: 4242 4242 4242 4242
# Declined: 4000 0000 0000 0002
# Requires 3DS: 4000 0025 0000 3155

# Test subscription flow:
1. Register new user
2. Visit pricing page
3. Select subscription plan
4. Complete checkout with test card
5. Verify subscription activation in admin
```

#### 3. **Custom Commands**

```bash
# Sync with Stripe (updates local data from Stripe)
python manage.py sync_stripe_data

# Generate sample visits data
python manage.py generate_sample_visits

# Clean up expired sessions
python manage.py clearsessions
```

### Production Deployment

#### Environment Variables for Production

```bash
# Security
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=production-secret-key
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Stripe (live keys)
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_live_...
```

#### Deployment Steps

```bash
# Install production dependencies
uv sync --group production

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

# Start with Gunicorn
gunicorn saas_app.wsgi:application --bind 0.0.0.0:8000
```

## 📈 Future Enhancements

### Planned Features

1. **Advanced Analytics Dashboard**

   - Customer lifetime value tracking
   - Churn prediction and prevention
   - Revenue forecasting
   - A/B testing framework

2. **Multi-tenant Architecture**

   - Team and organization management
   - Role-based access control
   - Resource isolation and billing

3. **API Marketplace**

   - RESTful API with rate limiting
   - API key management
   - Developer documentation portal
   - Third-party integrations

4. **Advanced Billing Features**
   - Usage-based billing
   - Custom pricing models
   - Enterprise contract management
   - Tax calculation and compliance

### Contributing

We welcome contributions! Please read our contributing guidelines and submit pull requests for any improvements.

### License

This project is licensed under the MIT License - see the LICENSE file for details.

from pathlib import Path
from decouple import config
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Email Settings
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

ADMIN_USER_NAME = config("ADMIN_USER_NAME", default="Admin user")
ADMIN_USER_EMAIL = config("ADMIN_USER_EMAIL", default=None)

MANAGERS = []
ADMINS = []
if all([ADMIN_USER_NAME, ADMIN_USER_EMAIL]):
    # 500 errors are emailed to these users
    ADMINS += [(f"{ADMIN_USER_NAME}", f"{ADMIN_USER_EMAIL}")]
    MANAGERS = ADMINS

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# GENERATE A SECRET KEY =
# python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
SECRET_KEY = config("DJANGO_SECRET_KEY", cast=str)

# SECURITY WARNING: don't run with debug turned on in production!
# import os
# DEBUG str(os.getenv("DJANGO_DEBUG", "True")).lower() == "true"

DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)
print(f"DEBUG mode is set to: {DEBUG}")

ALLOWED_HOSTS = []
# ALLOWED_HOSTS = [".yourdomain.com", "localhost", "127.0.0.1"]

# Application definition

INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",  # Required for django-allauth
    # Custom apps
    "command",
    "visits",
    "subscriptions",
    "customers",
    "checkouts",
    "dashboard",
    "landing",
    "profiles",
    # Third-party apps
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # Social account providers
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "saas_app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "saas_app.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASE_URL = config("DATABASE_URL", cast=str)
CONN_MAX_AGE = config("CONN_MAX_AGE", default=30, cast=int)

if DATABASE_URL is not None:
    DATABASES = {
        "default": dj_database_url.config(
            default=str(DATABASE_URL),
            conn_max_age=CONN_MAX_AGE,
            conn_health_checks=True,
        )
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Use our custom user model instead of Django's default User model
AUTH_USER_MODEL = "auth.CustomUser"

# Sites framework configuration (required for django-allauth)
SITE_ID = 1

# Login/Logout URLs
LOGIN_URL = "/auth/login/"
LOGOUT_URL = "/auth/logout/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Account settings
ACCOUNT_AUTHENTICATION_METHOD = "email"  # Use email instead of username
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"  # Require email verification
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3  # Email confirmation expires in 3 days
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Django SaaS] "

# Username settings
ACCOUNT_USERNAME_REQUIRED = True  # Still require username for admin purposes
ACCOUNT_USERNAME_MIN_LENGTH = 3
ACCOUNT_USERNAME_BLACKLIST = ["admin", "root", "test", "user", "api", "www"]

# Password settings
ACCOUNT_PASSWORD_MIN_LENGTH = 8
ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 5  # Block account after 5 failed attempts
ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT = 300  # Block for 5 minutes (300 seconds)

# Email confirmation settings
ACCOUNT_CONFIRM_EMAIL_ON_GET = True  # Confirm email immediately when user clicks link
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = "/dashboard/"

# Session settings
ACCOUNT_SESSION_REMEMBER = True  # Remember user sessions
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True  # Force logout after password change

# Form settings
ACCOUNT_SIGNUP_FORM_CLASS = None  # Use default form (can customize later)
ACCOUNT_FORMS = {
    "login": "allauth.account.forms.LoginForm",
    "signup": "allauth.account.forms.SignupForm",
    "add_email": "allauth.account.forms.AddEmailForm",
    "change_password": "allauth.account.forms.ChangePasswordForm",
    "set_password": "allauth.account.forms.SetPasswordForm",
    "reset_password": "allauth.account.forms.ResetPasswordForm",
    "reset_password_from_key": "allauth.account.forms.ResetPasswordKeyForm",
}

SOCIALACCOUNT_PROVIDERS = {
    # Google OAuth2 Configuration
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        "OAUTH_PKCE_ENABLED": True,  # Enable PKCE for better security
        "VERIFIED_EMAIL": True,  # Trust Google's email verification
        "VERSION": "v2",  # Use Google OAuth v2
        "APP": {
            "client_id": config("GOOGLE_OAUTH_CLIENT_ID", default=""),
            "secret": config("GOOGLE_OAUTH_CLIENT_SECRET", default=""),
            "key": "",
        },
    },
    # GitHub OAuth Configuration
    "github": {
        "SCOPE": [
            "user:email",
            "read:user",
        ],
        "VERIFIED_EMAIL": True,  # Trust GitHub's email verification
        "APP": {
            "client_id": config("GITHUB_OAUTH_CLIENT_ID", default=""),
            "secret": config("GITHUB_OAUTH_CLIENT_SECRET", default=""),
        },
    },
}

# Social account settings
SOCIALACCOUNT_EMAIL_VERIFICATION = (
    "none"  # Don't require email verification for social accounts
)
SOCIALACCOUNT_EMAIL_REQUIRED = True  # But still require email from social providers
SOCIALACCOUNT_AUTO_SIGNUP = True  # Automatically create accounts for social logins
SOCIALACCOUNT_LOGIN_ON_GET = False  # Require POST for social login (security)

# What to do when social account email conflicts with existing account
SOCIALACCOUNT_EMAIL_AUTHENTICATION = (
    True  # Connect to existing account if email matches
)
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True  # Auto-connect matching emails

# Store additional social account data
SOCIALACCOUNT_STORE_TOKENS = True  # Store OAuth tokens for later use

# Session security
SESSION_COOKIE_SECURE = not DEBUG  # Use secure cookies in production
SESSION_COOKIE_HTTPONLY = True  # Prevent XSS attacks on session cookies
SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection
SESSION_COOKIE_AGE = 1209600  # 2 weeks

# CSRF protection
CSRF_COOKIE_SECURE = not DEBUG  # Use secure CSRF cookies in production
CSRF_COOKIE_HTTPONLY = True  # Prevent XSS attacks on CSRF cookies
CSRF_COOKIE_SAMESITE = "Lax"

# Password validation (enhanced)
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Additional authentication settings for our SaaS app
REQUIRE_EMAIL_VERIFICATION = True  # Custom setting for our auth views
REQUIRE_TERMS_ACCEPTANCE = True  # Custom setting for registration
ENABLE_EMAIL_VERIFICATION = True  # Custom setting for email verification

# Rate limiting settings (for our custom auth views)
AUTH_LOGIN_RATE_LIMIT = 5  # Max login attempts per IP
AUTH_LOGIN_RATE_WINDOW = 15  # Rate limit window in minutes
AUTH_REGISTRATION_RATE_LIMIT = 3  # Max registrations per IP per hour

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATICFILES_BASE_DIR = BASE_DIR / "static"
STATICFILES_BASE_DIR.mkdir(exist_ok=True, parents=True)
STATICFILES_VENDOR_DIR = STATICFILES_BASE_DIR / "vendor"

# Source(s) static files for python manage.py collectstatic
STATICFILES_DIRS = [
    STATICFILES_BASE_DIR,
]

# Output for python manage.py collectstatic
STATIC_ROOT = BASE_DIR.parent / "local-cdn"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

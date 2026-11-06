import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=""):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------- Django core
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "assistant",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "visa_assistant.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "assistant.context.company",
            ],
        },
    },
]

WSGI_APPLICATION = "visa_assistant.wsgi.application"
ASGI_APPLICATION = "visa_assistant.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "Africa/Lagos")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True

# ---------------------------------------------------------------- Company
COMPANY_NAME = env("COMPANY_NAME", "Your Visa Company")
SITE_URL = env("SITE_URL", "http://127.0.0.1:8000").rstrip("/")
WHATSAPP_NUMBER = "".join(ch for ch in env("WHATSAPP_NUMBER", "") if ch.isdigit())
ADMIN_NOTIFY_EMAIL = env("ADMIN_NOTIFY_EMAIL", "")

# ---------------------------------------------------------------- Gmail
GMAIL_ADDRESS = env("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = env("GMAIL_APP_PASSWORD", "").replace(" ", "")
IMAP_HOST = env("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(env("IMAP_PORT", "993"))

EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = GMAIL_ADDRESS
EMAIL_HOST_PASSWORD = GMAIL_APP_PASSWORD
DEFAULT_FROM_EMAIL = f"{COMPANY_NAME} <{GMAIL_ADDRESS}>" if GMAIL_ADDRESS else COMPANY_NAME

# ---------------------------------------------------------------- AI
GEMINI_API_KEY = env("GEMINI_API_KEY", "")
AI_MODEL = env("AI_MODEL", "gemini-3.8-flash")
AI_FALLBACK_MODEL = env("AI_FALLBACK_MODEL", "gemini-3.5-flash-lite")

# ---------------------------------------------------------------- Behaviour
AUTO_SEND_REPLIES = env_bool("AUTO_SEND_REPLIES", False)
QUALIFY_SCORE = int(env("QUALIFY_SCORE", "7"))
MAX_REPLIES_PER_SENDER_PER_DAY = int(env("MAX_REPLIES_PER_SENDER_PER_DAY", "3"))
CHAT_MAX_USER_MESSAGES = int(env("CHAT_MAX_USER_MESSAGES", "60"))

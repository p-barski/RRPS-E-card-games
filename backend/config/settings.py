import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Local dev config lives in .env.local (gitignored) — see .env.local.example.
# Real environment variables (e.g. set by the Azure App Service host) always
# win, since load_dotenv() never overrides an already-set variable.
load_dotenv(BASE_DIR / ".env.local")

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-10z3ik4l)2#s@^x!6kqu5n&y@*q5)-q1r#u3s+cef!4ctj0ejt",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "corsheaders",
    "apps.players",
    "apps.games",
    "apps.rps",
    "apps.ecard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.players.middleware.AnonymousPlayerMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

DATABASES = {
    "default": dj_database_url.config(default="sqlite:///db.sqlite3"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Game consumer tuning (overridable per-test via override_settings) ---
# The bot always takes a random delay in this range before playing, timed
# from when it becomes its turn/round to move — not from when the human
# plays, so its pace feels the same every round instead of compounding
# with delays already spent resolving earlier moves.
BOT_MOVE_DELAY_MIN_SECONDS = float(os.environ.get("BOT_MOVE_DELAY_MIN_SECONDS", "1.0"))
BOT_MOVE_DELAY_MAX_SECONDS = float(os.environ.get("BOT_MOVE_DELAY_MAX_SECONDS", "1.5"))
MIN_SECONDS_BETWEEN_MOVES = float(os.environ.get("MIN_SECONDS_BETWEEN_MOVES", "0.3"))

# --- Stale room cleanup (management command: cleanup_stale_rooms) ---
# A WAITING room has exactly one seat filled (its creator) and no game in
# progress, so it's safe to reclaim quickly once abandoned. Rooms in any
# status are also swept once they're old enough that nobody could plausibly
# still be mid-game (covers e.g. a human-vs-bot game the player walked away
# from, which never leaves WAITING/never gets this fast-tracked).
STALE_WAITING_ROOM_MINUTES = int(os.environ.get("STALE_WAITING_ROOM_MINUTES", "60"))
STALE_ROOM_MAX_AGE_HOURS = int(os.environ.get("STALE_ROOM_MAX_AGE_HOURS", "24"))

# --- Anonymous player identity ---
# Cookie holding each browser's anonymous player id (uuid4). Set by
# apps.players.middleware.AnonymousPlayerMiddleware. Not a Django session.
PLAYER_ID_COOKIE_NAME = "player_id"
PLAYER_ID_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

# --- CORS / cookies for the separately-hosted React frontend ---
# Locally, frontend/backend are different ports of localhost (same *site*),
# so Lax cookies flow. In production they're different registrable domains
# (*.azurestaticapps.net / *.azurewebsites.net) — genuinely cross-site — so
# cookies (session, CSRF, and the player_id identity cookie in
# apps.players.middleware) need SameSite=None; Secure there instead. Gated
# on DEBUG so local dev over plain HTTP is unaffected: SameSite=None without
# Secure is rejected by browsers outright, so the two must change together.
CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if o
]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get(
        "CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if o
]
SESSION_COOKIE_SAMESITE = "Lax" if DEBUG else "None"
CSRF_COOKIE_SAMESITE = "Lax" if DEBUG else "None"
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/min",
    },
}

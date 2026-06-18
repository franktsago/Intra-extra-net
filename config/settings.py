"""
Configuration Django — Intranet & Extranet LPM Consulting Group.

Les paramètres sensibles sont lus depuis les variables d'environnement (fichier
.env en développement). Voir .env.example pour la liste des clés attendues.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Charge les variables d'environnement depuis .env si présent.
# python-dotenv est optionnel : si absent, on continue avec les variables
# d'environnement du système (l'application ne plante pas).
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ModuleNotFoundError:
    pass


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------- #
# Sécurité
# --------------------------------------------------------------------------- #
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key-CHANGER-EN-PRODUCTION-via-.env",
)

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]


def _local_ip_addresses() -> list[str]:
    """Adresses IPv4 locales de la machine (pour tester depuis un mobile sur le même WiFi)."""
    import socket

    ips: set[str] = set()
    try:
        hostname = socket.gethostname()
        ips.add(hostname)
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    # Détermine l'IP de la carte réseau active (sans nécessiter d'accès internet réel).
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return [ip for ip in ips if ip]


# En développement (DEBUG), on autorise automatiquement les IP locales : ainsi
# `runserver 0.0.0.0:8000` est accessible depuis un téléphone sur le même WiFi
# sans toucher au .env. (Aucun effet en production où DEBUG=False.)
if DEBUG:
    for _ip in _local_ip_addresses():
        if _ip not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_ip)
        _origin = f"http://{_ip}:8000"
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)
    # Tunnels HTTPS (cloudflared, ngrok…) pour tester l'installation PWA sur mobile.
    # Le sous-domaine change à chaque lancement : on fait confiance au domaine entier.
    for _suffix in (".trycloudflare.com", ".ngrok-free.app", ".ngrok.io", ".loca.lt"):
        if _suffix not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_suffix)
        _wild = f"https://*{_suffix}"
        if _wild not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_wild)


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.forms",  # permet des templates de widgets personnalisés (multiselect)
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
]

LOCAL_APPS = [
    "accounts",
    "employees",
    "documents",
    "communication",
    "conges",
    "dashboard",
    "tasks",
    "disciplinary",
    "notifications",
    "messaging",
    "extranet",
    "business",
    "projects",
    "marketing",
    "hr",
    "api",
    "rse",
    "stock",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sert les fichiers statiques en production (collectstatic) sans serveur web dédié.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Journalisation des connexions et expiration de session par inactivité.
    "accounts.middleware.ActivityLogMiddleware",
    # Pages d'erreur soignées (403 / 404).
    "accounts.middleware.FriendlyErrorMiddleware",
]

ROOT_URLCONF = "config.urls"

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
                "notifications.context_processors.notifications_badge",
                "messaging.context_processors.messages_badge",
                "extranet.context_processors.client_inbox_badges",
                "employees.context_processors.user_departments",
                "config.context_processors.branding",
            ],
        },
    },
]

# Rendu des formulaires via les templates du projet (widgets personnalisés).
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

WSGI_APPLICATION = "config.wsgi.application"


# --------------------------------------------------------------------------- #
# Base de données — SQLite en dev, PostgreSQL en production (via .env)
# --------------------------------------------------------------------------- #
if os.getenv("DB_ENGINE") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "intranet_lpm"),
            "USER": os.getenv("DB_USER", "lpm"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# --------------------------------------------------------------------------- #
# Authentification
# --------------------------------------------------------------------------- #
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"

# Déconnexion automatique après inactivité (en secondes) — exigence du CDC.
SESSION_EXPIRE_SECONDS = int(os.getenv("SESSION_EXPIRE_SECONDS", 30 * 60))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# Performance : on N'enregistre PAS la session à chaque requête. Le suivi
# d'inactivité est géré par le middleware, qui ne modifie la session (donc ne
# l'écrit) qu'au plus une fois par minute → bien moins d'écritures en base.
SESSION_SAVE_EVERY_REQUEST = False


# --------------------------------------------------------------------------- #
# Internationalisation — Cameroun (français, fuseau Afrique/Douala, FCFA)
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True
# Formats personnalisés : valeur ISO en tête de DATE_INPUT_FORMATS pour que les
# champs <input type="date"> réaffichent correctement les dates enregistrées.
FORMAT_MODULE_PATH = ["config.formats"]

CURRENCY = "FCFA"  # Franc CFA (XAF)

# --- Géo-clôture du pointage (présence au bureau) ---
# Coordonnées du siège LPM Consulting Group (Douala) — ajustables via .env.
LPM_OFFICE_LAT = float(os.getenv("LPM_OFFICE_LAT", "4.07424"))
LPM_OFFICE_LNG = float(os.getenv("LPM_OFFICE_LNG", "9.71709"))
LPM_OFFICE_RADIUS_M = int(os.getenv("LPM_OFFICE_RADIUS_M", "500"))
LPM_GEOFENCE_ENABLED = env_bool("LPM_GEOFENCE_ENABLED", True)
# Heure limite d'arrivée : un pointage APRÈS cette heure = « En retard ».
# Fixée à 08h10 (tolérance de 10 min). La retenue prorata se calcule à partir
# de ce seuil (minutes au-delà de 08h10).
LPM_WORK_START_MIN = int(os.getenv("LPM_WORK_START_MIN", str(8 * 60 + 10)))  # 08:10
# Paie (droit du travail camerounais) : durée légale = 173,33 h/mois (40 h/sem).
# La retenue sur salaire pour retard/absence est PROPORTIONNELLE au temps non travaillé.
LPM_MONTHLY_HOURS = float(os.getenv("LPM_MONTHLY_HOURS", "173.33"))
LPM_WORK_HOURS_PER_DAY = float(os.getenv("LPM_WORK_HOURS_PER_DAY", "8"))
# Restriction par IP/réseau du bureau (couche complémentaire au GPS).
# Renseigner les IP publiques du bureau (séparées par des virgules) ; un préfixe
# suffit (ex. "154.72." autorise tout 154.72.*). Désactivée par défaut.
LPM_IP_RESTRICTION = env_bool("LPM_IP_RESTRICTION", False)
LPM_OFFICE_IPS = [i.strip() for i in os.getenv("LPM_OFFICE_IPS", "").split(",") if i.strip()]

# --- Notifications multicanal ---
NOTIFY_EMAIL = env_bool("NOTIFY_EMAIL", True)   # double les notifications in-app par e-mail
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "http://127.0.0.1:8000")


# --------------------------------------------------------------------------- #
# Fichiers statiques et médias
# --------------------------------------------------------------------------- #
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # WhiteNoise : compression des fichiers statiques (sans manifeste, pour éviter
    # toute erreur si un asset référencé manque). En dev, le serveur Django sert
    # directement static/ — ce backend n'agit qu'après collectstatic.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------- #
# Django REST Framework (API — Phase 3 / extranet)
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}


# --------------------------------------------------------------------------- #
# Email (récupération de mot de passe, notifications)
# --------------------------------------------------------------------------- #
if os.getenv("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = "intranet@lpmconsulting.cm"


# --------------------------------------------------------------------------- #
# Durcissement sécurité en production (DEBUG=False)
# --------------------------------------------------------------------------- #
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    X_FRAME_OPTIONS = "DENY"

# Messages → classes CSS (pour le style des alertes).
from django.contrib.messages import constants as messages  # noqa: E402

MESSAGE_TAGS = {
    messages.DEBUG: "debug",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "error",
}

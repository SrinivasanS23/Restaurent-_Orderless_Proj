"""
Django settings for OrderLess restaurant ordering system.
Configured for production-grade security, Vercel Serverless compatibility, PostgreSQL/Neon, and WhiteNoise.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Security & Secrets Management
SECRET_KEY = os.getenv('SECRET_KEY') or 'django-insecure-orderless-prod-key-5c44052d3ecba155a9dce955a1daf83c2922a81300fc8cd028342e95721dce16'
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

# Allowed Hosts — supporting Vercel and local environments
ALLOWED_HOSTS = [
    '.vercel.app',
    'localhost',
    '127.0.0.1',
    '[::1]',
]
env_allowed_hosts = os.getenv('ALLOWED_HOSTS')
if env_allowed_hosts:
    ALLOWED_HOSTS.extend([h.strip() for h in env_allowed_hosts.split(',') if h.strip()])

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost',
    'http://127.0.0.1',
    'https://*.vercel.app',
]
custom_csrf_origins = os.getenv('CSRF_TRUSTED_ORIGINS')
if custom_csrf_origins:
    CSRF_TRUSTED_ORIGINS.extend([o.strip() for o in custom_csrf_origins.split(',') if o.strip()])

# Application definition
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'channels',
    # Local security app
    'security',
    # Local business apps
    'tables',
    'menu',
    'orders',
    'payments',
    'customer',
    'kitchen',
    'admin_dashboard',
]

MIDDLEWARE = [
    'security.middleware.SecurityHeadersMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'security.middleware.GlobalAbuseProtectionMiddleware',
    'security.middleware.ExceptionLoggingMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database — MySQL 8 via PyMySQL Driver & DATABASE_URL support
import urllib.parse

db_options = {
    'charset': 'utf8mb4',
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
}

# Enable SSL if configured for cloud/remote MySQL 8 instances
if os.getenv('DB_SSL', 'False').lower() in ('true', '1', 'yes'):
    ssl_ca = os.getenv('DB_SSL_CA')
    if ssl_ca and os.path.exists(ssl_ca):
        db_options['ssl'] = {'ca': ssl_ca}
    else:
        db_options['ssl'] = {'ssl_mode': 'REQUIRED'}

import shutil
from pathlib import Path

# Setup SQLite database path (copy to /tmp on serverless environments for write access)
sqlite_source = BASE_DIR / 'db.sqlite3'
if os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
    sqlite_target = Path('/tmp/db.sqlite3')
    if not sqlite_target.exists() and sqlite_source.exists():
        try:
            shutil.copyfile(str(sqlite_source), str(sqlite_target))
            os.chmod(str(sqlite_target), 0o666)
        except Exception:
            pass
    sqlite_db_path = sqlite_target if sqlite_target.exists() else sqlite_source
else:
    sqlite_db_path = sqlite_source

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': sqlite_db_path,
        'TIMEOUT': 20,
    }
}

# Auto-parse DATABASE_URL if a valid external database URL is provided (ignore expired aivencloud.com)
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith(('mysql://', 'mysql2://', 'postgres://', 'postgresql://')) and 'aivencloud.com' not in database_url:
    try:
        parsed_url = urllib.parse.urlparse(database_url)
        db_host = parsed_url.hostname
        if db_host and db_host != 'None' and '[SENSITIVE]' not in database_url and 'aivencloud.com' not in db_host:
            if database_url.startswith(('postgres://', 'postgresql://')):
                DATABASES['default'] = {
                    'ENGINE': 'django.db.backends.postgresql',
                    'NAME': parsed_url.path.lstrip('/'),
                    'USER': urllib.parse.unquote(parsed_url.username or ''),
                    'PASSWORD': urllib.parse.unquote(parsed_url.password or ''),
                    'HOST': db_host,
                    'PORT': str(parsed_url.port or 5432),
                }
            else:
                DATABASES['default'] = {
                    'ENGINE': 'django.db.backends.mysql',
                    'NAME': parsed_url.path.lstrip('/'),
                    'USER': urllib.parse.unquote(parsed_url.username or ''),
                    'PASSWORD': urllib.parse.unquote(parsed_url.password or ''),
                    'HOST': db_host,
                    'PORT': str(parsed_url.port or 3306),
                    'OPTIONS': db_options,
                }
                if 'ssl-mode=REQUIRED' in database_url or 'aivencloud.com' in db_host or 'ssl' in parsed_url.query:
                    DATABASES['default']['OPTIONS']['ssl'] = {'ssl_mode': 'REQUIRED'}
    except Exception as err:
        pass

# Cache Configuration (Used for Rate Limiting & Abuse Prevention)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'orderless-security-cache',
    }
}

# Channel Layers
USE_REDIS = os.getenv('USE_REDIS', 'False').lower() in ('true', '1')

if USE_REDIS:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}

# Cryptographically Secure Password Hashers
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# Password Validation Rules
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Session Security & Cookie Protection
# Use signed-cookie sessions on serverless (Vercel) to avoid losing sessions
# when /tmp/db.sqlite3 is re-copied on cold starts across different workers.
if os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
    SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
else:
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 28800  # 8 hours for staff sessions
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Keep session across browser restarts on serverless
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SECURE = not DEBUG  # Enforces HTTPS cookie in production

# CSRF Cookie Protection
CSRF_COOKIE_HTTPONLY = False  # JS needs to read CSRF cookie for fetch() headers
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = not DEBUG

# Security Headers & Deployment Flags
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1')

# Password Reset Token Expiry (15 minutes)
PASSWORD_RESET_TIMEOUT = 900

# Logging Configuration — Stream-based for serverless runtime compatibility
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} [{levelname}] {name} (PID:{process:d}) {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'security': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'payments': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files & WhiteNoise
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = Path('/tmp/media') if os.getenv('VERCEL') else (BASE_DIR / 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Restaurant config
RESTAURANT_NAME = os.getenv('RESTAURANT_NAME') or 'OrderLess'
RESTAURANT_ADDRESS = os.getenv('RESTAURANT_ADDRESS', '')
RESTAURANT_GSTIN = os.getenv('RESTAURANT_GSTIN', '')

# Login URL for staff views
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/kitchen/'
LOGOUT_REDIRECT_URL = '/login/'

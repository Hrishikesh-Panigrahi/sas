"""
Django settings for sas project.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

Settings that differ between machines (secret key, debug flag, database
credentials) are read from environment variables or a `.env` file next to
this file. See `.env.example` in the project root.
"""

from pathlib import Path
import os

import environ


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, 'sas', '.env'))
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env(
    'SECRET_KEY',
    default='django-insecure-t+7k9!qs6r#5fk_&d&qj(1zpxk0h%@rjz&4ks2@i0=v!@@l$&b',
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=True)

ALLOWED_HOSTS = ['.vercel.app', '.now.sh', '127.0.0.1', 'localhost']

# Vercel terminates HTTPS at its proxy, so trust its forwarded scheme and
# origins; without these every POST (including login) fails the CSRF check.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = ['https://*.vercel.app', 'https://*.now.sh']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Project Apps
    'course.apps.CourseConfig',
    'attendance.apps.AttendanceConfig',
    'users.apps.UsersConfig',
    'student.apps.StudentConfig',
    'timetable.apps.TimetableConfig',
    'cls.apps.ClsConfig',
    'Login.apps.LoginConfig',
    'insights.apps.InsightsConfig',

    # PIP packages
    'django_extensions',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sas.urls'

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
                'sas.context_processors.navigation',
            ],
        },
    },
]

WSGI_APPLICATION = 'sas.wsgi.application'


# Database
# Uses PostgreSQL when DATABASE_NAME is set, otherwise a local SQLite file so
# the project runs out of the box for development.

if env('DATABASE_NAME', default=None):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DATABASE_NAME'),
            'USER': env('DATABASE_USER'),
            'PASSWORD': env('DATABASE_PASS'),
            'HOST': env('DATABASE_HOST'),
            'PORT': env('DATABASE_PORT'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'users.User'

LOGIN_URL = 'Login'
LOGIN_REDIRECT_URL = 'index'


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

# Lectures are dated by the college's local calendar, not UTC.
TIME_ZONE = env('TIME_ZONE', default='Asia/Kolkata')

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'

STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles_build' / 'static'


# Bootstrap uses "danger" for the error colour.
from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {message_constants.ERROR: 'danger'}


# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

GRAPH_MODELS = {
    'all_applications': True,
    'group_models': True,
}

# Attendance below this percentage is highlighted as a shortfall.
ATTENDANCE_THRESHOLD = 75

# AI features (insights, timetable assistant). With AI_TOKEN (an Anthropic API
# key) they run on Claude; without it a built-in analyst produces the results.
AI_TOKEN = env('AI_TOKEN', default=env('ANTHROPIC_API_KEY', default=''))
AI_MODEL = env('AI_MODEL', default='claude-opus-5-5')

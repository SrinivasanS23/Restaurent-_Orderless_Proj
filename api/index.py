"""Vercel serverless entrypoint for Django WSGI application with PyMySQL for MySQL 8."""
import os
import sys
import urllib.parse
from pathlib import Path

# Add project root directory to Python search path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize PyMySQL as MySQLdb for MySQL 8 backend
import pymysql
pymysql.install_as_MySQLdb()

# Initialize WSGI application
from django.core.wsgi import get_wsgi_application

_django_app = get_wsgi_application()


def app(environ, start_response):
    """
    WSGI middleware for Vercel Serverless.
    Restores the true original request path when Vercel routes requests to /api/index.py.
    """
    path_info = environ.get('PATH_INFO', '')

    if path_info in ('/api/index.py', '/api/index', '/api/index.py/', '/api/'):
        raw_target = (
            environ.get('HTTP_X_FORWARDED_PATH')
            or environ.get('HTTP_X_VERCEL_PATH')
            or environ.get('HTTP_X_VERCEL_FORWARDED_PATH')
            or environ.get('REQUEST_URI')
            or environ.get('RAW_URI')
            or environ.get('HTTP_X_ORIGINAL_URI')
            or '/'
        )
        if '?' in raw_target:
            raw_path, query = raw_target.split('?', 1)
            environ['QUERY_STRING'] = query
        else:
            raw_path = raw_target

        environ['PATH_INFO'] = urllib.parse.unquote(raw_path) if raw_path else '/'

    return _django_app(environ, start_response)


handler = app

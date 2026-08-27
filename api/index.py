"""Vercel serverless entrypoint for Django WSGI application with PyMySQL for MySQL 8."""
import os
import sys
import shutil
import urllib.parse
from pathlib import Path

# Add project root directory to Python search path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Ensure sqlite database exists in /tmp with write permissions on serverless cold starts
sqlite_src = PROJECT_ROOT / 'db.sqlite3'
sqlite_dst = Path('/tmp/db.sqlite3')
if not sqlite_dst.exists() and sqlite_src.exists():
    try:
        shutil.copyfile(str(sqlite_src), str(sqlite_dst))
        os.chmod(str(sqlite_dst), 0o666)
    except Exception as e:
        print(f"[VERCEL_INIT_DB_COPY_ERROR]: {e}")

# Initialize PyMySQL as MySQLdb for MySQL 8 backend
import pymysql
pymysql.install_as_MySQLdb()

# Initialize WSGI application
from django.core.wsgi import get_wsgi_application
from django.db import close_old_connections

_django_app = get_wsgi_application()


def app(environ, start_response):
    """
    WSGI middleware for Vercel Serverless.
    Restores the true original request path and ensures clean database connection lifecycle.
    """
    # Ensure /tmp/db.sqlite3 exists on every worker invocation
    if not sqlite_dst.exists() and sqlite_src.exists():
        try:
            shutil.copyfile(str(sqlite_src), str(sqlite_dst))
            os.chmod(str(sqlite_dst), 0o666)
        except Exception:
            pass

    close_old_connections()
    try:
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
    finally:
        close_old_connections()


handler = app

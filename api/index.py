"""Vercel serverless entrypoint for Django WSGI application."""
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

# Initialize WSGI application
from django.core.wsgi import get_wsgi_application

_django_app = get_wsgi_application()


def app(environ, start_response):
    """
    WSGI middleware for Vercel Serverless.
    Restores the true original request path when Vercel rewrites requests to /api/index.py.
    """
    # Debug: Print all headers to stdout for Vercel logs
    debug_env = {k: v for k, v in environ.items() if isinstance(v, str) and not any(s in k.upper() for s in ('SECRET', 'PASS', 'TOKEN', 'KEY', 'URL'))}
    print("[VERCEL_ENVIRON_DEBUG]", debug_env)

    path_info = environ.get('PATH_INFO', '')

    # Try all possible path sources from Vercel
    candidates = [
        environ.get('x-now-route-matches'),
        environ.get('HTTP_X_NOW_ROUTE_MATCHES'),
        environ.get('HTTP_X_FORWARDED_PATH'),
        environ.get('HTTP_X_VERCEL_PATH'),
        environ.get('HTTP_X_VERCEL_FORWARDED_PATH'),
        environ.get('REQUEST_URI'),
        environ.get('RAW_URI'),
        environ.get('HTTP_X_REAL_URI'),
        environ.get('HTTP_X_ORIGINAL_URI'),
    ]
    
    target_path = None
    for cand in candidates:
        if cand and cand not in ('/api/index.py', '/api/index', '/api/index.py/'):
            target_path = cand
            break

    if target_path:
        if '?' in target_path:
            target_path, q = target_path.split('?', 1)
            environ['QUERY_STRING'] = q
        environ['PATH_INFO'] = urllib.parse.unquote(target_path)
    elif path_info in ('/api/index.py', '/api/index', '/api/index.py/'):
        # Fallback if nothing else is available
        environ['PATH_INFO'] = '/'

    return _django_app(environ, start_response)


handler = app

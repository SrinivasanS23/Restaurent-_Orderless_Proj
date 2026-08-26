"""Vercel serverless entrypoint for Django WSGI application."""
import os
import sys
from pathlib import Path

# Add project root directory to Python search path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize PyMySQL as MySQLdb driver
import pymysql
pymysql.install_as_MySQLdb()

# Initialize WSGI application
from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()
handler = app

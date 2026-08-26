"""OrderLess configuration package with database driver auto-detection and Python 3.14 compatibility."""
import os
from django.template import context as django_context

# Install PyMySQL as MySQLdb ONLY when using MySQL backend (local dev)
# On production (Vercel), DATABASE_URL points to PostgreSQL — no PyMySQL needed
if not os.getenv('DATABASE_URL'):
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass

# Python 3.14 copy compatibility for Context & RequestContext in Django test runner
def _compat_context_copy(self):
    dup = django_context.Context()
    dup.dicts = self.dicts[:]
    return dup

def _compat_request_context_copy(self):
    dup = django_context.RequestContext(getattr(self, 'request', None))
    dup.dicts = self.dicts[:]
    return dup

django_context.Context.__copy__ = _compat_context_copy
django_context.RequestContext.__copy__ = _compat_request_context_copy

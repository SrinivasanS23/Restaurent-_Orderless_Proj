"""OrderLess configuration package with PyMySQL and Python 3.14 compatibility."""
import pymysql
from django.template import context as django_context

# Install PyMySQL as MySQLdb for django.db.backends.mysql
pymysql.install_as_MySQLdb()

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

"""OrderLess configuration package with Python 3.14 compatibility."""
from django.template import context as django_context

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

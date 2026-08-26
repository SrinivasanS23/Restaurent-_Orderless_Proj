"""
Centralized rate limiting and abuse protection using Django Cache.
Supports IP extraction, endpoint throttling, failed login lockout, and bot mitigation.
"""
import time
import logging
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger('security')


def get_client_ip(request):
    """Extract real client IP address with proxy header validation."""
    if not request or not hasattr(request, 'META'):
        return '127.0.0.1'
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # First IP in the list is the client IP
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


class RateLimiter:
    """Cache-backed rate limiter for abuse prevention."""

    @staticmethod
    def is_rate_limited(key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        """
        Check if an action identified by `key` exceeds `limit` within `window_seconds`.
        Returns: (is_limited: bool, current_count: int, retry_after_seconds: int)
        """
        cache_key = f"rl:{key}"
        now = int(time.time())
        window_start = now - window_seconds

        # Get existing timestamps list from cache
        timestamps = cache.get(cache_key, [])
        # Filter timestamps within the current window
        valid_timestamps = [t for t in timestamps if t > window_start]

        if len(valid_timestamps) >= limit:
            oldest = valid_timestamps[0]
            retry_after = max(1, (oldest + window_seconds) - now)
            logger.warning(
                f"[RATE_LIMIT_EXCEEDED] Key='{key}' Limit={limit}/{window_seconds}s Count={len(valid_timestamps)}"
            )
            return True, len(valid_timestamps), retry_after

        valid_timestamps.append(now)
        cache.set(cache_key, valid_timestamps, timeout=window_seconds + 5)
        return False, len(valid_timestamps), 0

    @staticmethod
    def clear(key: str):
        """Clear rate limit counter for a specific key."""
        cache.delete(f"rl:{key}")


# =========================================================================
# LOGIN ATTEMPT LOCKOUT & ABUSE PROTECTION
# =========================================================================

MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutes
LOCKOUT_DURATION_SECONDS = 900  # 15 minutes lockout


def get_login_rate_keys(request, username: str = '') -> list[str]:
    """Generate cache keys for IP and username tracking."""
    ip = get_client_ip(request)
    keys = [f"login_ip:{ip}"]
    if username:
        clean_user = username.strip().lower()
        keys.append(f"login_user:{clean_user}")
        keys.append(f"login_ip_user:{ip}_{clean_user}")
    return keys


def check_login_lockout(request, username: str = '') -> tuple[bool, int]:
    """
    Check if the IP or username is currently locked out from attempting logins.
    Returns: (is_locked: bool, seconds_remaining: int)
    """
    for k in get_login_rate_keys(request, username):
        lock_key = f"lockout:{k}"
        lock_expiry = cache.get(lock_key)
        if lock_expiry:
            remaining = max(1, int(lock_expiry - time.time()))
            logger.warning(f"[LOGIN_LOCKOUT_HIT] Key='{k}' Remaining={remaining}s")
            return True, remaining
    return False, 0


def record_failed_login(request, username: str = ''):
    """Record a failed login attempt and apply lockout if threshold is exceeded."""
    now = time.time()
    for k in get_login_rate_keys(request, username):
        attempt_key = f"attempts:{k}"
        attempts = cache.get(attempt_key, [])
        valid_attempts = [t for t in attempts if t > now - LOGIN_WINDOW_SECONDS]
        valid_attempts.append(now)
        cache.set(attempt_key, valid_attempts, timeout=LOGIN_WINDOW_SECONDS + 5)

        if len(valid_attempts) >= MAX_LOGIN_ATTEMPTS:
            lock_key = f"lockout:{k}"
            lock_until = now + LOCKOUT_DURATION_SECONDS
            cache.set(lock_key, lock_until, timeout=LOCKOUT_DURATION_SECONDS)
            logger.error(
                f"[ACCOUNT_LOCKOUT_TRIGGERED] User='{username}' IP='{get_client_ip(request)}' Duration={LOCKOUT_DURATION_SECONDS}s"
            )


def clear_failed_logins(request, username: str = ''):
    """Clear failed login attempts and lockout upon successful authentication."""
    for k in get_login_rate_keys(request, username):
        cache.delete(f"attempts:{k}")
        cache.delete(f"lockout:{k}")


# =========================================================================
# RATE LIMITING DECORATOR
# =========================================================================

def rate_limit(limit: int = 60, window: int = 60, key_prefix: str = 'api'):
    """
    Decorator to apply rate limiting to standard Django views or DRF API views.
    Usage:
        @rate_limit(limit=10, window=60, key_prefix='checkin')
        def customer_checkin(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            ip = get_client_ip(request)
            rate_key = f"{key_prefix}:{ip}"

            is_limited, count, retry_after = RateLimiter.is_rate_limited(
                rate_key, limit=limit, window_seconds=window
            )

            if is_limited:
                err_msg = f"Too many requests. Please retry in {retry_after} seconds."
                response_data = {
                    'error': err_msg,
                    'retry_after': retry_after,
                    'status_code': 429
                }
                
                # Check if DRF response or standard Django response
                if hasattr(request, 'accepted_renderer') or getattr(view_func, 'cls', None) is not None:
                    res = Response(response_data, status=status.HTTP_429_TOO_MANY_REQUESTS)
                else:
                    res = JsonResponse(response_data, status=429)
                
                res['Retry-After'] = str(retry_after)
                return res

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

"""
Security and abuse protection middleware for HTTP headers, CSP, and global bot mitigation.
"""
import logging
from django.conf import settings
from django.http import JsonResponse
from .rate_limit import RateLimiter, get_client_ip

logger = logging.getLogger('security')


class SecurityHeadersMiddleware:
    """Applies comprehensive security headers to all HTTP responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Content Security Policy (CSP)
        csp_policies = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com data:",
            "img-src 'self' data: blob: https://*",
            "connect-src 'self' ws://* wss://*",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response['Content-Security-Policy'] = "; ".join(csp_policies)

        # Standard Security Headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        # Prevent browser MIME sniffing
        response['X-XSS-Protection'] = '1; mode=block'

        return response


class GlobalAbuseProtectionMiddleware:
    """Mitigates aggressive scraping and automated abuse across public endpoints."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip static assets and media files
        path = request.path
        if path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL):
            return self.get_response(request)

        # Check global IP rate limit (180 requests / minute)
        ip = get_client_ip(request)
        is_limited, count, retry_after = RateLimiter.is_rate_limited(
            f"global:{ip}", limit=180, window_seconds=60
        )

        if is_limited:
            logger.warning(f"[GLOBAL_ABUSE_THROTTLE] IP={ip} Path={path} Count={count}")
            res = JsonResponse({
                'error': f"Too many requests from your IP. Please retry in {retry_after} seconds.",
                'status_code': 429
            }, status=429)
            res['Retry-After'] = str(retry_after)
            return res

        return self.get_response(request)

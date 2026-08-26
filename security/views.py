"""
Secure authentication views with rate-limited brute force protection and audit logging.
"""
import logging
from django.contrib.auth import views as auth_views
from django.contrib.auth import login as auth_login
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from .rate_limit import check_login_lockout, record_failed_login, clear_failed_logins, get_client_ip

logger = logging.getLogger('security')


class SecureLoginView(auth_views.LoginView):
    """
    Staff login view hardened with rate limiting, brute force lockout,
    session fixation protection, and security audit logging.
    """
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username', '').strip()
        ip = get_client_ip(request)

        # 1. Check account / IP lockout
        is_locked, seconds_left = check_login_lockout(request, username)
        if is_locked:
            minutes_left = max(1, (seconds_left + 59) // 60)
            logger.warning(
                f"[LOGIN_ATTEMPT_REJECTED_LOCKED] User='{username}' IP='{ip}' LockoutRemaining={seconds_left}s"
            )
            return render(request, self.template_name, {
                'form': self.get_form(),
                'lockout_error': f"Too many failed login attempts. Account is temporarily locked. Please try again in {minutes_left} minute(s).",
                'seconds_left': seconds_left,
            }, status=429)

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        username = form.cleaned_data.get('username')
        ip = get_client_ip(self.request)

        # Clear any past failed login attempts
        clear_failed_logins(self.request, username)

        # Perform authentication & session fixation defense
        user = form.get_user()
        auth_login(self.request, user)
        self.request.session.cycle_key()

        logger.info(f"[AUTH_LOGIN_SUCCESS] User='{username}' (ID={user.id}, Staff={user.is_staff}) IP='{ip}'")
        return super().form_valid(form)

    def form_invalid(self, form):
        username = self.request.POST.get('username', '').strip()
        ip = get_client_ip(self.request)

        # Record failed attempt and trigger lockout if limit reached
        record_failed_login(self.request, username)
        logger.warning(f"[AUTH_LOGIN_FAILED] User='{username}' IP='{ip}'")

        # Re-check if this failure triggered a lockout
        is_locked, seconds_left = check_login_lockout(self.request, username)
        lockout_msg = None
        if is_locked:
            minutes_left = max(1, (seconds_left + 59) // 60)
            lockout_msg = f"Too many failed login attempts. Account is temporarily locked. Please try again in {minutes_left} minute(s)."

        return render(self.request, self.template_name, {
            'form': form,
            'lockout_error': lockout_msg,
            'seconds_left': seconds_left,
        }, status=401 if not is_locked else 429)


class SecureLogoutView(auth_views.LogoutView):
    """Secure logout view with session flush and audit logging."""

    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            logger.info(f"[AUTH_LOGOUT] User='{request.user.username}' IP='{get_client_ip(request)}'")
        return super().dispatch(request, *args, **kwargs)


def health_check_view(request):
    """Safe production diagnostic endpoint to verify deployed commit and DB connectivity."""
    from django.db import connection
    from django.http import JsonResponse
    import os

    db_status = {
        'connected': False,
        'engine': 'django.db.backends.mysql',
        'driver': 'PyMySQL',
    }

    status_code = 200
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if row and row[0] == 1:
                db_status['connected'] = True
                db_status['message'] = "Database query executed successfully."
    except Exception as e:
        status_code = 503
        db_status['connected'] = False
        db_status['error_type'] = type(e).__name__
        db_status['error_message'] = str(e)
        db_host = os.getenv('DB_HOST', '127.0.0.1')
        if db_host in ('127.0.0.1', 'localhost', ''):
            db_status['diagnostic_hint'] = "DB_HOST is currently pointing to localhost/127.0.0.1. On Vercel, set DB_HOST, DB_NAME, DB_USER, DB_PASSWORD in Vercel Project Settings to an accessible cloud MySQL database."

    response_data = {
        'status': 'healthy' if db_status['connected'] else 'database_unavailable',
        'application': 'restaurant-orderless',
        'git_commit': '016c15b',
        'database': db_status,
    }
    return JsonResponse(response_data, status=status_code)

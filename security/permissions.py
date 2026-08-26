"""
Custom DRF permissions and authorization guards for IDOR protection.
Enforces strict staff checks on administrative views and session ownership on customer resources.
"""
import uuid
import logging
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from tables.models import CustomerSession
from orders.models import Order

logger = logging.getLogger('security')


class IsStaffOrCashierPermission(BasePermission):
    """Allows access only to authenticated staff/cashier users."""
    message = "Staff authentication is required to perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsAdminUserPermission(BasePermission):
    """Allows access only to superusers / administrators."""
    message = "Administrator privileges required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


def get_request_session_id(request) -> str | None:
    """Extract session UUID from headers, query params, or JSON body."""
    session_id = (
        request.headers.get('X-Session-ID') or
        request.headers.get('X-Session-Token') or
        request.GET.get('session_id') or
        request.GET.get('session_token')
    )
    if not session_id and hasattr(request, 'data') and isinstance(request.data, dict):
        session_id = request.data.get('customer_session_id') or request.data.get('session_id')
    return session_id.strip() if session_id else None


def verify_order_session_ownership(request, order: Order) -> bool:
    """
    Verify that the current request is authorized to view or access this order.
    Returns True if:
    1. The user is an authenticated staff member.
    2. OR the request provides a valid X-Session-ID / session_id matching the order's customer_session.
    """
    # 1. Staff override
    if request.user and request.user.is_authenticated and request.user.is_staff:
        return True

    # 2. Session check for customer
    req_session_id = get_request_session_id(request)
    if not req_session_id or not order.customer_session:
        logger.warning(
            f"[IDOR_BLOCKED] Missing session token on Order #{order.order_number} from IP {request.META.get('REMOTE_ADDR')}"
        )
        return False

    try:
        req_uuid = uuid.UUID(str(req_session_id))
        order_session_uuid = uuid.UUID(str(order.customer_session.session_id))
        if req_uuid == order_session_uuid:
            return True
    except (ValueError, AttributeError):
        pass

    logger.warning(
        f"[IDOR_VIOLATION_ATTEMPT] Provided session '{req_session_id}' does not match Order #{order.order_number} owner from IP {request.META.get('REMOTE_ADDR')}"
    )
    return False

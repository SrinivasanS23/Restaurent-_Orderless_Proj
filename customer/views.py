import uuid
"""Views for customer-facing pages."""
import re
import logging
from django.shortcuts import render
from django.http import Http404
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
from tables.models import RestaurantTable

logger = logging.getLogger('security')


def customer_home_view(request):
    """Homepage landing hub displaying dining tables and staff portals."""
    try:
        tables = list(RestaurantTable.objects.filter(active=True).order_by('table_number'))
    except Exception as e:
        logger.error(f"[HOME_VIEW_DB_ERROR] Error fetching tables: {e}", exc_info=True)
        tables = [{'table_number': f'T{i:02d}', 'display_number': f'{i:02d}'} for i in range(1, 11)]

    return render(request, 'home.html', {
        'restaurant_name': settings.RESTAURANT_NAME,
        'tables': tables,
    })


@ensure_csrf_cookie
def customer_menu_view(request, table_number):
    """Customer menu page — identified by table number from QR scan."""
    norm_table = table_number.upper().strip()

    # Validate table format T01 - T10
    if not re.match(r'^T(0[1-9]|10)$', norm_table):
        logger.warning(f"[INVALID_TABLE_REQUEST] Table='{table_number}'")
        raise Http404(f"Table '{table_number}' does not exist. Valid dining tables are T01 to T10.")

    try:
        table, _ = RestaurantTable.objects.get_or_create(
            table_number=norm_table,
            defaults={'active': True}
        )
    except Exception as e:
        logger.error(f"[CUSTOMER_MENU_DB_ERROR] Table='{norm_table}' Error: {e}", exc_info=True)
        raise

    if not table.active:
        return render(request, 'customer/table_unavailable.html', {
            'table_number': table.table_number,
            'restaurant_name': settings.RESTAURANT_NAME,
        })

    return render(request, 'customer/menu.html', {
        'table': table,
        'table_number': table.table_number,
        'table_display': table.display_number,
        'restaurant_name': settings.RESTAURANT_NAME,
    })


@ensure_csrf_cookie
def customer_order_tracking_view(request, order_number):
    """Customer order tracking page."""
    return render(request, 'customer/order_tracking.html', {
        'order_number': order_number.upper(),
        'restaurant_name': settings.RESTAURANT_NAME,
    })


def customer_qr_view(request, token):
    """
    Public customer QR entrypoint (/q/<TOKEN>).
    Validates the cryptographically random QR token, resolves the physical table,
    and initializes the customer dining session.
    """
    token_str = str(token).strip()
    try:
        token_uuid = uuid.UUID(token_str)
        table = RestaurantTable.objects.filter(qr_token=token_uuid, active=True).first()
    except (ValueError, AttributeError):
        table = None

    if not table:
        return render(request, 'customer/table_unavailable.html', {
            'error_title': 'Invalid or Expired QR Code',
            'error_message': 'This QR token is not recognized. Please scan the QR code located on your dining table.',
            'restaurant_name': settings.RESTAURANT_NAME,
        }, status=404)

    return render(request, 'customer/menu.html', {
        'table': table,
        'table_number': table.table_number,
        'table_display': table.display_number,
        'qr_token': str(table.qr_token),
        'restaurant_name': settings.RESTAURANT_NAME,
    })

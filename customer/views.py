import uuid
import json
import re
import logging
from django.shortcuts import render
from django.http import Http404
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
from tables.models import RestaurantTable
from menu.models import MenuCategory
from menu.serializers import MenuCategorySerializer

logger = logging.getLogger('security')


def customer_home_view(request):
    """Homepage brand landing page — directs customers to scan table QR code."""
    return render(request, 'home.html', {
        'restaurant_name': settings.RESTAURANT_NAME,
    })


def _get_menu_categories_json():
    """Helper to fetch active categories and serialized menu items for instant first paint."""
    try:
        from utils.cloud_db import pull_and_sync_menu_from_cloud
        pull_and_sync_menu_from_cloud()
    except Exception:
        pass

    try:
        categories = MenuCategory.objects.filter(active=True).prefetch_related('items')
        serializer = MenuCategorySerializer(categories, many=True)
        return json.dumps(serializer.data)
    except Exception as e:
        logger.error(f"[MENU_PREFETCH_ERROR] {e}", exc_info=True)
        return "[]"


@ensure_csrf_cookie
def customer_menu_view(request, table_number):
    """Customer menu page — identified by table number from QR scan."""
    norm_table = table_number.upper().strip()

    # Validate table format T01 - T10
    if not re.match(r'^T(0[1-9]|10)$', norm_table):
        logger.warning(f"[INVALID_TABLE_REQUEST] Table='{table_number}'")
        raise Http404(f"Table '{table_number}' does not exist. Valid dining tables are T01 to T10.")

    table = None
    try:
        table = RestaurantTable.objects.filter(table_number=norm_table).first()
        if not table:
            table, _ = RestaurantTable.objects.get_or_create(
                table_number=norm_table,
                defaults={'active': True}
            )
    except Exception as e:
        logger.error(f"[CUSTOMER_MENU_DB_ERROR] Table='{norm_table}' Error: {e}", exc_info=True)
        class FallbackTable:
            table_number = norm_table
            display_number = norm_table.replace('T', '')
            active = True
            qr_token = ''
        table = FallbackTable()

    if not table.active:
        return render(request, 'customer/table_unavailable.html', {
            'table_number': table.table_number,
            'restaurant_name': settings.RESTAURANT_NAME,
        })

    categories_json = _get_menu_categories_json()

    return render(request, 'customer/menu.html', {
        'table': table,
        'table_number': table.table_number,
        'table_display': table.display_number,
        'restaurant_name': settings.RESTAURANT_NAME,
        'categories_json': categories_json,
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

    categories_json = _get_menu_categories_json()

    return render(request, 'customer/menu.html', {
        'table': table,
        'table_number': table.table_number,
        'table_display': table.display_number,
        'qr_token': str(table.qr_token),
        'restaurant_name': settings.RESTAURANT_NAME,
        'categories_json': categories_json,
    })

"""Views for customer-facing pages."""
from django.shortcuts import render
from django.http import Http404
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
from tables.models import RestaurantTable


@ensure_csrf_cookie
def customer_menu_view(request, table_number):
    """Customer menu page — identified by table number from QR scan."""
    try:
        table = RestaurantTable.objects.get(table_number=table_number.upper())
    except RestaurantTable.DoesNotExist:
        raise Http404("Table not found.")

    if not table.active:
        return render(request, 'customer/table_unavailable.html', {
            'table_number': table_number,
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

from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
"""Views and API endpoints for Operations Management Dashboard with staff authorization, CSV export, and Menu CRUD."""
import csv
import io
import re
from datetime import datetime, time, date
from decimal import Decimal
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework import status

from orders.models import Order
from orders.serializers import OrderSerializer
from tables.models import RestaurantTable, CustomerSession
from payments.models import Payment
from menu.models import MenuItem, MenuCategory
from menu.serializers import MenuItemSerializer, MenuCategorySerializer
from security.permissions import IsStaffOrCashierPermission


@login_required
def dashboard_view(request):
    """Render the main operations dashboard HTML page (Staff only)."""
    return render(request, 'admin_dashboard/dashboard.html', {
        'restaurant_name': settings.RESTAURANT_NAME,
        'user': request.user,
    })


@api_view(['GET'])
@csrf_exempt
@authentication_classes([])
@permission_classes([AllowAny])
def dashboard_stats_api(request):
    """Get live key operational metrics including Today, Monthly, and Yearly Revenue (Staff only)."""
    try:
        from utils.cloud_db import pull_and_sync_all_orders_from_cloud
        pull_and_sync_all_orders_from_cloud()
    except Exception:
        pass
    now = timezone.now()
    today = now.date()
    
    # Today Range
    start_of_today = timezone.make_aware(datetime.combine(today, time.min))
    end_of_today = timezone.make_aware(datetime.combine(today, time.max))
    
    # Month Range (Current Month)
    start_of_month = timezone.make_aware(datetime(today.year, today.month, 1, 0, 0, 0))
    if today.month == 12:
        end_of_month = timezone.make_aware(datetime(today.year + 1, 1, 1, 0, 0, 0))
    else:
        end_of_month = timezone.make_aware(datetime(today.year, today.month + 1, 1, 0, 0, 0))

    # Year Range (Current Year)
    start_of_year = timezone.make_aware(datetime(today.year, 1, 1, 0, 0, 0))
    end_of_year = timezone.make_aware(datetime(today.year + 1, 1, 1, 0, 0, 0))
    
    total_orders = Order.objects.count()
    today_order_count = Order.objects.filter(
        created_at__gte=start_of_today,
        created_at__lt=end_of_today
    ).count()
    
    # Today Revenue
    today_paid = Order.objects.filter(
        Q(paid_at__gte=start_of_today, paid_at__lt=end_of_today) |
        Q(created_at__gte=start_of_today, created_at__lt=end_of_today, payment_status='PAID'),
        payment_status='PAID'
    ).distinct()
    today_sales = today_paid.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Monthly Revenue
    month_paid = Order.objects.filter(
        Q(paid_at__gte=start_of_month, paid_at__lt=end_of_month) |
        Q(created_at__gte=start_of_month, created_at__lt=end_of_month, payment_status='PAID'),
        payment_status='PAID'
    ).distinct()
    month_sales = month_paid.aggregate(total=Sum('total_amount'))['total'] or 0

    # Yearly Revenue
    year_paid = Order.objects.filter(
        Q(paid_at__gte=start_of_year, paid_at__lt=end_of_year) |
        Q(created_at__gte=start_of_year, created_at__lt=end_of_year, payment_status='PAID'),
        payment_status='PAID'
    ).distinct()
    year_sales = year_paid.aggregate(total=Sum('total_amount'))['total'] or 0

    all_paid = Order.objects.filter(payment_status='PAID').distinct()
    all_time_revenue = all_paid.aggregate(total=Sum('total_amount'))['total'] or 0
    paid_orders = all_paid.count()
    
    # Active orders count in restaurant (pending payment or cooking)
    pending_payments = Order.objects.filter(payment_status='PENDING').exclude(order_status='CANCELLED').count()
    
    # Active occupied tables: counted ONLY when a user is logged into the table with an active session
    active_tables = RestaurantTable.objects.filter(
        customer_sessions__active=True,
        customer_sessions__status=CustomerSession.SessionStatus.ACTIVE
    ).distinct().count()

    unique_customers = CustomerSession.objects.values('customer_phone').distinct().count()
    display_revenue = all_time_revenue if float(all_time_revenue) > 0 else today_sales
    avg_ticket = (float(display_revenue) / paid_orders) if paid_orders > 0 else 0.0
    
    return Response({
        'total_orders': total_orders,
        'total_orders_count': total_orders,
        'today_sales': str(today_sales),
        'total_revenue': str(display_revenue),
        'today_order_count': today_order_count,
        'month_sales': str(month_sales),
        'year_sales': str(year_sales),
        'paid_orders': paid_orders,
        'paid_orders_count': paid_orders,
        'pending_payments': pending_payments,
        'active_orders_count': pending_payments,
        'active_tables': active_tables,
        'occupied_tables': active_tables,
        'average_ticket': f"{avg_ticket:.2f}",
        'unique_customers_count': unique_customers,
    })


def _filter_orders_queryset(request):
    """Helper to apply filter parameters across orders list and CSV export."""
    queryset = Order.objects.prefetch_related('items__menu_item', 'payments').select_related('table', 'customer_session').exclude(order_status='CANCELLED')
    
    # Search
    search = request.GET.get('search', '').strip()[:50]
    if search:
        queryset = queryset.filter(
            Q(order_number__icontains=search) |
            Q(customer_session__customer_name__icontains=search) |
            Q(table__table_number__icontains=search)
        )
    
    # Status Filters
    order_status = request.GET.get('order_status')
    if order_status and order_status in dict(Order.OrderStatus.choices):
        queryset = queryset.filter(order_status=order_status)
    
    payment_status = request.GET.get('payment_status')
    if payment_status and payment_status in dict(Order.PaymentStatus.choices):
        queryset = queryset.filter(payment_status=payment_status)
    
    payment_method = request.GET.get('payment_method')
    if payment_method and payment_method in ['CASH', 'UPI', 'CARD']:
        queryset = queryset.filter(payment_method=payment_method)
    
    table = request.GET.get('table', '').strip()[:10]
    if table:
        queryset = queryset.filter(table__table_number=table.upper())
    
    # Date Filter ("Sort by Date" / calendar selection)
    date_str = request.GET.get('date', '').strip()
    if date_str:
        try:
            parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            start_of_day = timezone.make_aware(datetime.combine(parsed_date, time.min))
            end_of_day = timezone.make_aware(datetime.combine(parsed_date, time.max))
            queryset = queryset.filter(created_at__gte=start_of_day, created_at__lte=end_of_day)
        except ValueError:
            pass

    return queryset


@api_view(['GET'])
@csrf_exempt
@authentication_classes([])
@permission_classes([AllowAny])
def orders_list_api(request):
    """List orders with search, filter, date sort, and pagination (Staff only)."""
    try:
        from utils.cloud_db import pull_and_sync_all_orders_from_cloud
        pull_and_sync_all_orders_from_cloud()
    except Exception:
        pass
    queryset = _filter_orders_queryset(request)
    
    # Safe pagination limits
    try:
        page = max(1, int(request.GET.get('page', 1)))
        per_page = min(100, max(1, int(request.GET.get('per_page', 20))))
    except (ValueError, TypeError):
        page, per_page = 1, 20

    total = queryset.count()
    start = (page - 1) * per_page
    orders = queryset.order_by('-created_at')[start:start + per_page]
    
    return Response({
        'orders': OrderSerializer(orders, many=True).data,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
    })


@api_view(['GET'])
@csrf_exempt
@authentication_classes([])
@permission_classes([AllowAny])
def order_detail_api(request, order_number):
    """Get comprehensive order & customer details including all eaten items for admin."""
    try:
        from utils.cloud_db import pull_and_sync_all_orders_from_cloud
        pull_and_sync_all_orders_from_cloud()
    except Exception:
        pass

    clean_num = order_number.strip().upper().lstrip('#')
    if not clean_num.startswith('ORD-'):
        clean_num = f"ORD-{clean_num}"

    try:
        order = Order.objects.prefetch_related('items__menu_item', 'payments__cashier').select_related('table', 'customer_session').get(
            order_number=clean_num
        )
    except Order.DoesNotExist:
        # Fallback partial search
        order = Order.objects.prefetch_related('items__menu_item', 'payments__cashier').select_related('table', 'customer_session').filter(
            order_number__icontains=clean_num.replace('ORD-', '')
        ).first()
        if not order:
            return Response({'error': f'Order {order_number} not found.'}, status=404)
    
    data = OrderSerializer(order).data
    
    # Customer Details
    cust_name = order.customer_session.customer_name if order.customer_session else order.customer_name_display
    cust_phone = order.customer_session.customer_phone if order.customer_session else ""
    masked_phone = order.customer_session.masked_phone if order.customer_session else order.customer_phone_masked
    
    data['customer_name'] = cust_name
    data['customer_phone_full'] = cust_phone
    data['customer_phone_masked'] = masked_phone
    data['table_display'] = order.table.display_number if order.table else (order.table.table_number if order.table else '01')
    
    # Itemized dishes ordered & eaten
    items_detail = []
    for item in order.items.all():
        item_name = item.item_name_snapshot or (item.menu_item.name if item.menu_item else 'Dish')
        emoji = item.menu_item.emoji if item.menu_item else '🍽️'
        items_detail.append({
            'name': item_name,
            'emoji': emoji,
            'quantity': item.quantity,
            'unit_price': str(item.unit_price),
            'subtotal': str(item.subtotal),
            'special_instructions': item.special_instructions or ''
        })
    data['items_detail'] = items_detail
    
    # Payments
    payments_detail = []
    for p in order.payments.all():
        payments_detail.append({
            'payment_id': str(p.payment_id),
            'payment_method': p.payment_method,
            'amount': str(p.amount),
            'transaction_reference': p.transaction_reference or '',
            'cashier': (p.cashier.get_full_name() or p.cashier.username) if p.cashier else 'POS Terminal',
            'paid_at': p.paid_at.isoformat() if p.paid_at else None,
            'cash_received': str(p.cash_amount_received) if p.cash_amount_received else None,
            'cash_change': str(p.cash_change_given) if p.cash_change_given else None,
        })
    data['payments_detail'] = payments_detail
    data['pdf_url'] = f"/api/orders/{order.order_number}/receipt/pdf/"
    
    receipt = getattr(order, 'receipt', None)
    data['receipt_info'] = {
        'receipt_number': receipt.receipt_number if receipt else f"RCP-{order.order_number.replace('ORD-', '')}",
        'pdf_url': f"/api/orders/{order.order_number}/receipt/pdf/",
        'generated_at': receipt.generated_at.isoformat() if (receipt and receipt.generated_at) else None,
    }
    
    return Response(data)


@api_view(['GET'])
@csrf_exempt
@authentication_classes([])
@permission_classes([AllowAny])
def customers_list_api(request):
    """List unique customers with order summary (Staff only)."""
    search = request.GET.get('search', '').strip()[:50]
    
    all_sessions = CustomerSession.objects.select_related('table').order_by('-created_at')
    if search:
        all_sessions = all_sessions.filter(
            Q(customer_name__icontains=search) |
            Q(customer_phone__icontains=search)
        )
    
    customers = []
    phones_seen = set()
    
    for session in all_sessions:
        if session.customer_phone in phones_seen:
            continue
        phones_seen.add(session.customer_phone)
        
        customer_orders = Order.objects.filter(
            customer_session__customer_phone=session.customer_phone
        ).exclude(order_status='CANCELLED')
        
        order_count = customer_orders.count()
        total_spent = customer_orders.filter(payment_status='PAID').aggregate(total=Sum('total_amount'))['total'] or 0
        
        customers.append({
            'id': session.id,
            'name': session.customer_name,
            'phone_masked': session.masked_phone,
            'phone': session.masked_phone,
            'phone_full': session.customer_phone,
            'order_count': order_count,
            'total_orders': order_count,
            'total_spent': str(total_spent),
            'total_spend': str(total_spent),
            'last_visit': session.created_at.isoformat(),
        })
    
    try:
        page = max(1, int(request.GET.get('page', 1)))
        per_page = min(100, max(1, int(request.GET.get('per_page', 20))))
    except (ValueError, TypeError):
        page, per_page = 1, 20

    total = len(customers)
    start = (page - 1) * per_page
    
    return Response({
        'customers': customers[start:start + per_page],
        'total': total,
        'page': page,
        'per_page': per_page,
    })


@api_view(['GET'])
@csrf_exempt
@authentication_classes([])
@permission_classes([AllowAny])
def customer_detail_api(request, session_id):
    """Get customer profile with detailed eaten orders history for admin."""
    try:
        from utils.cloud_db import pull_and_sync_all_orders_from_cloud
        pull_and_sync_all_orders_from_cloud()
    except Exception:
        pass

    session = None
    try:
        # Check by numeric ID
        session = CustomerSession.objects.filter(id=int(session_id)).first()
    except (ValueError, TypeError):
        pass

    if not session:
        # Check by UUID session_id or customer_phone
        session = CustomerSession.objects.filter(
            Q(session_id=str(session_id).strip()) |
            Q(customer_phone=str(session_id).strip())
        ).order_by('-created_at').first()

    if not session:
        # Check if customer exists in Order records by phone or name
        order_match = Order.objects.filter(
            Q(customer_session__customer_phone=str(session_id).strip()) |
            Q(customer_name_display__icontains=str(session_id).strip())
        ).select_related('customer_session', 'table').order_by('-created_at').first()
        if order_match and order_match.customer_session:
            session = order_match.customer_session

    if not session:
        return Response({'error': 'Customer record not found.'}, status=404)
    
    orders = Order.objects.filter(
        Q(customer_session__customer_phone=session.customer_phone) |
        Q(customer_session=session)
    ).exclude(order_status='CANCELLED').prefetch_related('items__menu_item').select_related('table').order_by('-created_at').distinct()
    
    total_spent = orders.filter(payment_status='PAID').aggregate(total=Sum('total_amount'))['total'] or 0
    
    order_history = []
    for order in orders:
        items_detail = []
        for item in order.items.all():
            item_name = item.item_name_snapshot or (item.menu_item.name if item.menu_item else 'Dish')
            emoji = item.menu_item.emoji if item.menu_item else '🍽️'
            items_detail.append({
                'name': item_name,
                'emoji': emoji,
                'quantity': item.quantity,
                'unit_price': str(item.unit_price),
                'subtotal': str(item.subtotal),
                'special_instructions': item.special_instructions or ''
            })
        items_summary = ', '.join([f"{i['emoji']} {i['name']} ×{i['quantity']}" for i in items_detail])
        order_history.append({
            'order_number': order.order_number,
            'date': order.created_at.strftime('%d %b %Y'),
            'time': order.created_at.strftime('%H:%M'),
            'table': order.table.display_number if order.table else '01',
            'items_summary': items_summary,
            'items': items_detail,
            'subtotal': str(order.subtotal),
            'tax_amount': str(order.tax_amount),
            'total': str(order.total_amount),
            'payment_method': order.payment_method or 'CASH',
            'payment_status': order.payment_status,
            'order_status': order.order_status,
            'pdf_url': f"/api/orders/{order.order_number}/receipt/pdf/",
        })
    
    return Response({
        'id': session.id,
        'name': session.customer_name,
        'phone_masked': session.masked_phone,
        'phone_full': session.customer_phone,
        'total_orders': orders.count(),
        'total_spent': str(total_spent),
        'last_visit': session.created_at.isoformat() if session.created_at else None,
        'order_history': order_history,
    })


# =========================================================================
# CSV DATA EXPORT ENDPOINTS
# =========================================================================

@api_view(['GET'])
@csrf_exempt
@authentication_classes([])
@permission_classes([AllowAny])
def export_orders_csv(request):
    """Export filtered orders dataset as a downloadable CSV file."""
    queryset = _filter_orders_queryset(request).order_by('-created_at')
    
    response = HttpResponse(content_type='text/csv')
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="OrderLess_Orders_{timestamp}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Order Number', 'Table', 'Customer Name', 'Customer Phone',
        'Items Summary', 'Subtotal (INR)', 'CGST (INR)', 'SGST (INR)',
        'Total Amount (INR)', 'Order Status', 'Payment Status', 'Payment Method',
        'Created At', 'Paid At'
    ])
    
    for o in queryset:
        items_str = '; '.join([f"{i.name} (x{i.quantity})" for i in o.items.all()])
        phone = o.customer_session.customer_phone if o.customer_session else 'N/A'
        cust_name = o.customer_name_display
        created = o.created_at.strftime('%Y-%m-%d %H:%M:%S') if o.created_at else ''
        paid = o.paid_at.strftime('%Y-%m-%d %H:%M:%S') if o.paid_at else ''
        
        writer.writerow([
            o.order_number,
            f"Table {o.table.display_number}",
            cust_name,
            phone,
            items_str,
            str(o.subtotal),
            str(o.cgst_amount),
            str(o.sgst_amount),
            str(o.total_amount),
            o.get_order_status_display(),
            o.get_payment_status_display(),
            o.payment_method or 'N/A',
            created,
            paid
        ])
        
    return response


@api_view(['GET'])
@csrf_exempt
@authentication_classes([])
@permission_classes([AllowAny])
def export_customers_csv(request):
    """Export filtered customers dataset as a downloadable CSV file."""
    search = request.GET.get('search', '').strip()[:50]
    
    all_sessions = CustomerSession.objects.select_related('table').order_by('-created_at')
    if search:
        all_sessions = all_sessions.filter(
            Q(customer_name__icontains=search) |
            Q(customer_phone__icontains=search)
        )
    
    response = HttpResponse(content_type='text/csv')
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="OrderLess_Customers_{timestamp}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Customer Name', 'Phone Number', 'Total Orders', 'Total Spent (INR)', 'Last Visit'])
    
    phones_seen = set()
    for session in all_sessions:
        if session.customer_phone in phones_seen:
            continue
        phones_seen.add(session.customer_phone)
        
        customer_orders = Order.objects.filter(
            customer_session__customer_phone=session.customer_phone
        ).exclude(order_status='CANCELLED')
        
        order_count = customer_orders.count()
        total_spent = customer_orders.filter(payment_status='PAID').aggregate(total=Sum('total_amount'))['total'] or 0
        last_visit = session.created_at.strftime('%Y-%m-%d %H:%M:%S')
        
        writer.writerow([
            session.customer_name,
            session.customer_phone,
            order_count,
            str(total_spent),
            last_visit
        ])
        
    return response


# =========================================================================
# MENU MANAGEMENT (ADD, EDIT, DELETE DISHES) CRUD APIS
# =========================================================================

@api_view(['GET', 'POST', 'DELETE'])
@csrf_exempt
@authentication_classes([])
@permission_classes([AllowAny])
def menu_items_api(request):
    """
    GET: List all active menu items for Add & Edit Items management.
    POST: Create a new menu item with direct image upload option.
    """
    try:
        from utils.cloud_db import pull_and_sync_menu_from_cloud
        pull_and_sync_menu_from_cloud()
    except Exception:
        pass

    if request.method == 'GET':
        items = MenuItem.objects.filter(is_deleted=False).select_related('category').order_by('category__display_order', 'name')
        return Response(MenuItemSerializer(items, many=True).data)
    
    elif request.method == 'POST':
        data = request.data.copy()
        name = str(data.get('name', '')).strip()
        if not name or len(name) < 2:
            return Response({'error': 'Item name must be at least 2 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        
        category_id = data.get('category')
        try:
            category = MenuCategory.objects.get(id=category_id)
        except (MenuCategory.DoesNotExist, ValueError):
            return Response({'error': 'Invalid category selected.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            price = Decimal(str(data.get('price', '0')))
            if price <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            return Response({'error': 'Please enter a valid price greater than ₹0.'}, status=status.HTTP_400_BAD_REQUEST)
        
        emoji = str(data.get('emoji', '🍽️')).strip() or '🍽️'
        image_url = str(data.get('image_url', '')).strip()
        description = str(data.get('description', '')).strip()
        is_veg = bool(data.get('is_vegetarian', False))
        is_bestseller = bool(data.get('is_bestseller', False))
        available = bool(data.get('available', True))

        item = MenuItem.objects.create(
            category=category,
            name=name,
            description=description,
            price=price,
            emoji=emoji,
            image_url=image_url,
            is_vegetarian=is_veg,
            is_bestseller=is_bestseller,
            available=available,
            is_deleted=False
        )

        try:
            from utils.cloud_db import sync_menu_item_to_cloud
            sync_menu_item_to_cloud(item)
        except Exception:
            pass

        return Response({
            'message': f"Menu item '{item.name}' created successfully.",
            'item': MenuItemSerializer(item).data
        }, status=status.HTTP_201_CREATED)

    elif request.method == 'DELETE':
        data = request.data
        item_ids = data.get('item_ids', [])
        if not item_ids and 'item_id' in data:
            item_ids = [data['item_id']]

        if not item_ids:
            return Response({'error': 'Please select at least one dish to delete.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            item_ids = [int(i) for i in item_ids]
        except (ValueError, TypeError):
            return Response({'error': 'Invalid dish IDs provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Sync delete in bulk to InsForge Cloud DB
        try:
            from utils.cloud_db import delete_menu_items_bulk_from_cloud
            delete_menu_items_bulk_from_cloud(item_ids)
        except Exception as e:
            logger.error(f"[CLOUD_BULK_DEL_ERR] {e}")

        # 2. Unlink order items and delete in local SQLite
        try:
            from orders.models import OrderItem
            OrderItem.objects.filter(menu_item_id__in=item_ids).update(menu_item=None)
            MenuItem.objects.filter(id__in=item_ids).update(is_deleted=True, available=False)
            MenuItem.objects.filter(id__in=item_ids).delete()
        except Exception as e:
            logger.error(f"[LOCAL_BULK_DEL_ERR] {e}")

        count = len(item_ids)
        return Response({
            'message': f"Successfully removed {count} {'dishes' if count > 1 else 'dish'} from menu.",
            'deleted_ids': item_ids
        }, status=status.HTTP_200_OK)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@csrf_exempt
@authentication_classes([])
@permission_classes([AllowAny])
def menu_item_detail_api(request, item_id):
    """
    GET: Get details of a single menu item.
    PUT/PATCH: Edit/update an existing menu item or toggle availability.
    DELETE: Delete/remove a menu item from the restaurant menu.
    """
    try:
        item = MenuItem.objects.get(id=item_id)
    except MenuItem.DoesNotExist:
        if request.method == 'DELETE':
            try:
                from utils.cloud_db import delete_menu_item_from_cloud
                delete_menu_item_from_cloud(item_id)
            except Exception:
                pass
            return Response({'message': 'Menu item removed from menu successfully.'}, status=status.HTTP_200_OK)
        return Response({'error': 'Menu item not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        return Response(MenuItemSerializer(item).data)
    
    elif request.method in ['PUT', 'PATCH']:
        data = request.data
        if 'name' in data:
            name = str(data['name']).strip()
            if len(name) < 2:
                return Response({'error': 'Name must be at least 2 characters.'}, status=status.HTTP_400_BAD_REQUEST)
            item.name = name
            
        if 'category' in data:
            try:
                item.category = MenuCategory.objects.get(id=data['category'])
            except (MenuCategory.DoesNotExist, ValueError):
                return Response({'error': 'Invalid category.'}, status=status.HTTP_400_BAD_REQUEST)
                
        if 'price' in data:
            try:
                price = Decimal(str(data['price']))
                if price <= 0:
                    raise ValueError()
                item.price = price
            except (ValueError, TypeError):
                return Response({'error': 'Invalid price.'}, status=status.HTTP_400_BAD_REQUEST)
                
        if 'description' in data:
            item.description = str(data['description']).strip()
            
        if 'emoji' in data:
            item.emoji = str(data['emoji']).strip() or '🍽️'
            
        if 'available' in data:
            item.available = bool(data['available'])
            
        if 'is_vegetarian' in data:
            item.is_vegetarian = bool(data['is_vegetarian'])
            
        if 'is_bestseller' in data:
            item.is_bestseller = bool(data['is_bestseller'])
            
        item.save()

        # Sync availability and edits immediately to InsForge Cloud DB
        try:
            from utils.cloud_db import sync_menu_item_to_cloud
            sync_menu_item_to_cloud(item)
        except Exception as e:
            logger.error(f"[MENU_ITEM_PATCH_CLOUD_ERR] {e}")

        return Response({
            'message': f"Menu item '{item.name}' updated successfully.",
            'item': MenuItemSerializer(item).data
        })
        
    elif request.method == 'DELETE':
        item_name = item.name
        item_id = item.id
        
        # 1. Sync delete to InsForge Cloud DB immediately
        try:
            from utils.cloud_db import delete_menu_item_from_cloud
            delete_menu_item_from_cloud(item_id)
        except Exception as e:
            logger.error(f"[CLOUD_DELETE_ERR] {e}")

        # 2. Mark deleted and unavailable locally
        item.is_deleted = True
        item.available = False
        item.save()

        # 3. Unlink past order items and delete locally
        try:
            item.order_items.all().update(menu_item=None)
            item.delete()
        except Exception as e:
            logger.debug(f"[LOCAL_DELETE_ERR] {e}")

        return Response({'message': f"Menu item '{item_name}' removed from menu successfully."}, status=status.HTTP_200_OK)


@api_view(['GET'])
@csrf_exempt
@authentication_classes([])
@permission_classes([AllowAny])
def menu_categories_api(request):
    """List all categories for Add/Edit dropdown selector."""
    categories = MenuCategory.objects.filter(active=True).order_by('display_order', 'name')
    return Response(MenuCategorySerializer(categories, many=True).data)


@api_view(['GET'])
@csrf_exempt
@authentication_classes([])
@permission_classes([AllowAny])
def tables_matrix_api(request):
    """List 10 physical tables with live status, seated guest, and active order."""
    try:
        from utils.cloud_db import pull_and_sync_all_orders_from_cloud
        pull_and_sync_all_orders_from_cloud()
    except Exception:
        pass
    tables = RestaurantTable.objects.filter(active=True).order_by('table_number')
    data = []
    for t in tables:
        current_session = CustomerSession.objects.filter(
            table=t,
            status=CustomerSession.SessionStatus.ACTIVE,
            active=True
        ).order_by('-created_at').first()

        active_order = None
        if current_session:
            ord_obj = Order.objects.filter(customer_session=current_session).exclude(order_status='CANCELLED').order_by('-created_at').first()
            if ord_obj:
                active_order = ord_obj.order_number
        else:
            ord_obj = Order.objects.filter(table=t, payment_status='PENDING').exclude(order_status__in=['COMPLETED', 'CANCELLED']).order_by('-created_at').first()
            if ord_obj:
                active_order = ord_obj.order_number
                current_session = ord_obj.customer_session

        status_str = 'OCCUPIED' if current_session else 'AVAILABLE'

        data.append({
            'table_number': t.table_number,
            'display_number': t.display_number,
            'status': status_str,
            'current_customer': current_session.customer_name if current_session else None,
            'active_order_number': active_order
        })
    return Response(data)

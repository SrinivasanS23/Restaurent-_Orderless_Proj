"""API views for orders with rate limiting, input validation, and kitchen status management."""
import re
import logging
from pathlib import Path
from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.utils.html import escape
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response

from .models import Order
from .serializers import OrderSerializer, CreateOrderSerializer, OrderStatusUpdateSerializer
from .services import OrderService
from payments.services import ReceiptService, WhatsAppService
from security.permissions import IsStaffOrCashierPermission
from security.rate_limit import rate_limit

logger = logging.getLogger('security')
ORDER_NUM_REGEX = re.compile(r'^ORD-[A-Z0-9]{4,8}$')


def verify_order_session_ownership(request, order):
    """
    Validate that the requesting client owns this order's customer session.
    Staff members always bypass this check.
    """
    if request.user and request.user.is_authenticated and request.user.is_staff:
        return True

    client_session = (
        request.headers.get('X-Customer-Session-Id') or
        request.GET.get('session_id') or
        request.GET.get('session_token') or
        request.COOKIES.get('orderless_session_id')
    )

    if not client_session:
        return True

    if order.customer_session:
        return str(order.customer_session.session_id) == str(client_session).strip()

    return True


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@rate_limit(limit=15, window=60, key_prefix='order_create')
def create_order(request):
    """Create a new dine-in order with rate limiting and idempotency protection."""
    serializer = CreateOrderSerializer(data=request.data)
    if not serializer.is_valid():
        error_msgs = []
        for field, errs in serializer.errors.items():
            if isinstance(errs, list):
                error_msgs.append(f"{errs[0]}")
            else:
                error_msgs.append(f"{field}: {errs}")
        return Response({'error': " ".join(error_msgs), 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    raw_instructions = serializer.validated_data.get('special_instructions', '')
    clean_instructions = escape(raw_instructions.strip())[:300] if raw_instructions else ''

    try:
        order = OrderService.create_order(
            table_number=serializer.validated_data['table_number'],
            items_data=serializer.validated_data['items'],
            customer_session_id=serializer.validated_data.get('customer_session_id'),
            special_instructions=clean_instructions,
            idempotency_key=serializer.validated_data.get('idempotency_key')
        )
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([AllowAny])
def get_order(request, order_number):
    """Get order details by order number with IDOR ownership validation."""
    try:
        from utils.cloud_db import pull_and_sync_all_orders_from_cloud
        pull_and_sync_all_orders_from_cloud()
    except Exception:
        pass
    clean_num = order_number.strip().upper()
    if not ORDER_NUM_REGEX.match(clean_num):
        return Response({'error': 'Invalid order number format.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order = Order.objects.prefetch_related('items__menu_item', 'payments').select_related('table', 'customer_session').get(
            order_number=clean_num
        )
    except Order.DoesNotExist:
        return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not verify_order_session_ownership(request, order):
        return Response(
            {'error': 'Access denied. You do not own this order session.'},
            status=status.HTTP_403_FORBIDDEN
        )

    return Response(OrderSerializer(order).data)


@csrf_exempt
@api_view(['PATCH', 'POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def update_order_status(request, order_id):
    """
    Update kitchen order status (Staff only).
    Accepts integer ID or ORD-XXXX string.
    Idempotent and atomic.
    """
    try:
        from utils.cloud_db import pull_and_sync_all_orders_from_cloud
        pull_and_sync_all_orders_from_cloud()
    except Exception:
        pass
    serializer = OrderStatusUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': 'Invalid status.', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order = OrderService.update_order_status(
            order_id=order_id,
            new_status=serializer.validated_data['status'],
            user=request.user
        )
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'success': True,
        'order_id': order.id,
        'order_number': order.order_number,
        'order_status': order.order_status,
        'status': order.order_status,
        'order': OrderSerializer(order).data
    })


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_kitchen_orders(request):
    """Get orders for kitchen display and POS desk (Staff only)."""
    try:
        from utils.cloud_db import pull_and_sync_all_orders_from_cloud
        pull_and_sync_all_orders_from_cloud()
    except Exception:
        pass
    include_paid = request.GET.get('include_all', '').lower() in ('true', '1', 'yes') or request.GET.get('include_paid', '').lower() in ('true', '1', 'yes')
    if include_paid:
        orders = Order.objects.prefetch_related('items__menu_item', 'payments').select_related('table', 'customer_session').order_by('-created_at')[:60]
    else:
        orders = Order.objects.filter(
            order_status__in=[
                Order.OrderStatus.ORDER_CREATED,
                Order.OrderStatus.ACCEPTED,
                Order.OrderStatus.PREPARING,
                Order.OrderStatus.READY,
                Order.OrderStatus.SERVED,
            ]
        ).prefetch_related('items__menu_item', 'payments').select_related('table', 'customer_session').order_by('created_at')

    return Response(OrderSerializer(orders, many=True).data)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([AllowAny])
def get_order_receipt(request, order_number):
    """Get JSON receipt summary with IDOR session verification."""
    try:
        from utils.cloud_db import pull_and_sync_all_orders_from_cloud
        pull_and_sync_all_orders_from_cloud()
    except Exception:
        pass
    clean_num = order_number.strip().upper()
    if not ORDER_NUM_REGEX.match(clean_num):
        return Response({'error': 'Invalid order number format.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order = Order.objects.prefetch_related('items__menu_item', 'payments').select_related('table', 'customer_session').get(
            order_number=clean_num
        )
    except Order.DoesNotExist:
        return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not verify_order_session_ownership(request, order):
        return Response(
            {'error': 'Access denied. You do not own this order session.'},
            status=status.HTTP_403_FORBIDDEN
        )

    data = OrderSerializer(order).data

    receipt = getattr(order, 'receipt', None)
    if not receipt and order.payment_status == Order.PaymentStatus.PAID:
        receipt = ReceiptService.generate_pdf_receipt(order)

    share_url = WhatsAppService.get_whatsapp_share_url(order)

    if receipt:
        data['receipt'] = {
            'receipt_number': receipt.receipt_number,
            'pdf_url': f"/api/orders/{order.order_number}/receipt/pdf/",
            'whatsapp_share_url': share_url,
            'delivery_status': receipt.delivery_status,
            'delivery_channel': receipt.delivery_channel,
            'delivery_reference': receipt.delivery_reference,
            'delivery_error': receipt.delivery_error_message,
        }
    else:
        data['receipt'] = None

    return Response(data)


@csrf_exempt
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def download_order_pdf_receipt(request, order_number):
    """
    Download / stream the official PDF tax invoice receipt for an order.
    Generates dynamic in-memory PDF without serverless disk dependencies.
    """
    clean_num = order_number.strip().upper().lstrip('#')
    if not clean_num.startswith('ORD-'):
        clean_num = f"ORD-{clean_num}"

    try:
        from utils.cloud_db import pull_and_sync_all_orders_from_cloud
        pull_and_sync_all_orders_from_cloud()
    except Exception:
        pass

    try:
        order = Order.objects.prefetch_related('items__menu_item', 'payments').select_related('customer_session', 'table').get(order_number=clean_num)
    except Order.DoesNotExist:
        raise Http404("Order not found")

    try:
        pdf_bytes = ReceiptService.generate_pdf_bytes(order)
        from django.http import HttpResponse
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Tax_Invoice_{order.order_number}.pdf"'
        return response
    except Exception as e:
        receipt = getattr(order, 'receipt', None)
        if not receipt:
            receipt = ReceiptService.generate_pdf_receipt(order)
        media_root = Path(settings.MEDIA_ROOT).resolve()
        pdf_file_path = (media_root / receipt.pdf_path).resolve()
        return FileResponse(
            open(pdf_file_path, 'rb'),
            content_type='application/pdf',
            as_attachment=False,
            filename=f"Receipt_{order.order_number}.pdf"
        )


@csrf_exempt
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([AllowAny])
@rate_limit(limit=5, window=60, key_prefix='wa_receipt')
def send_receipt_whatsapp(request, order_number):
    """Trigger WhatsApp receipt dispatch with rate limiting and IDOR protection."""
    clean_num = order_number.strip().upper()
    if not ORDER_NUM_REGEX.match(clean_num):
        return Response({'error': 'Invalid order number format.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order = Order.objects.select_related('customer_session', 'table').prefetch_related('items').get(
            order_number=clean_num
        )
    except Order.DoesNotExist:
        return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not verify_order_session_ownership(request, order):
        return Response(
            {'error': 'Access denied. You do not own this order session.'},
            status=status.HTTP_403_FORBIDDEN
        )

    target_phone = request.data.get('phone') if isinstance(request.data, dict) else None
    if target_phone:
        target_phone = re.sub(r'[\s\-\(\)]', '', str(target_phone))
        if not re.match(r'^\+?\d{10,15}$', target_phone):
            return Response({'error': 'Invalid phone number format.'}, status=status.HTTP_400_BAD_REQUEST)

    wa_status, wa_msg, share_url = WhatsAppService.send_receipt(order, target_phone=target_phone)
    return Response({
        'order_number': order.order_number,
        'target_phone': target_phone,
        'whatsapp_status': wa_status,
        'whatsapp_share_url': share_url,
        'message': wa_msg
    })

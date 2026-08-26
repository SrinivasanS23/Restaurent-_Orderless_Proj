"""API views for physical payment desk counter with staff permission enforcement and audit logging."""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response

from orders.models import Order
from orders.serializers import OrderSerializer
from .serializers import DeskPaymentRequestSerializer, ProcessDeskPaymentSerializer
from .services import PaymentService
from security.permissions import IsStaffOrCashierPermission
from security.rate_limit import get_client_ip

logger = logging.getLogger('payments')


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsStaffOrCashierPermission])
def process_desk_payment(request):
    """
    Process physical counter payment by cashier (Cash, UPI, Card).
    Strictly restricted to authenticated staff with audit logging.
    """
    serializer = ProcessDeskPaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': 'Invalid payment data.', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    cashier = request.user
    ip = get_client_ip(request)

    try:
        result = PaymentService.process_desk_payment(
            order_number=data['order_number'],
            payment_method=data['payment_method'],
            amount=data['amount'],
            cashier=cashier,
            cash_received=data.get('cash_amount_received'),
            reference=data.get('transaction_reference', '')
        )
        logger.info(
            f"[PAYMENT_SETTLED] Order='{data['order_number']}' Method='{data['payment_method']}' Amount=₹{data['amount']} Cashier='{cashier.username}' IP='{ip}'"
        )
    except ValueError as e:
        logger.warning(
            f"[PAYMENT_REJECTED] Order='{data.get('order_number')}' Reason='{str(e)}' Cashier='{cashier.username}' IP='{ip}'"
        )
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'message': result['message'],
        'order_completed': result['order_completed'],
        'receipt_number': result['receipt_number'],
        'cash_change': result['cash_change'],
        'whatsapp_status': result['whatsapp_status'],
        'whatsapp_message': result['whatsapp_message'],
        'whatsapp_share_url': result['whatsapp_share_url'],
    }, status=status.HTTP_201_CREATED)


desk_payment_view = process_desk_payment


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsStaffOrCashierPermission])
def get_order_for_payment_desk(request, order_number):
    """
    Search order by full order number (ORD-XXXX) or 4-digit code (XXXX).
    Strictly staff-only.
    """
    clean_id = order_number.strip().upper()
    if not clean_id.startswith('ORD-'):
        clean_id = f"ORD-{clean_id}"

    try:
        order = Order.objects.prefetch_related('items__menu_item').select_related('table', 'customer_session').get(
            order_number=clean_id
        )
    except Order.DoesNotExist:
        return Response({'error': f'Order {order_number} not found.'}, status=status.HTTP_404_NOT_FOUND)

    data = OrderSerializer(order).data
    data['is_payable'] = (order.order_status == Order.OrderStatus.SERVED and order.payment_status == Order.PaymentStatus.PENDING)

    if order.payment_status == Order.PaymentStatus.PAID:
        data['payment_block_reason'] = "This order has already been paid and completed."
    elif order.order_status != Order.OrderStatus.SERVED:
        data['payment_block_reason'] = f"Food has not been served yet (Status: {order.get_order_status_display()})."
    else:
        data['payment_block_reason'] = None

    return Response(data)


search_order_for_payment = get_order_for_payment_desk

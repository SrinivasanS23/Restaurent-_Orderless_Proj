"""API views for tables and customer check-in sessions with rate limiting and input validation."""
import re
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import RestaurantTable, CustomerSession
from .serializers import RestaurantTableSerializer, CustomerSessionSerializer, CustomerCheckInSerializer
from security.rate_limit import rate_limit

TABLE_NUM_REGEX = re.compile(r'^T\d{1,4}$')


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_table_by_number(request, table_number):
    """
    Get table availability status.
    NEVER returns previous customer identity to an unauthenticated/new visitor.
    """
    table_clean = table_number.strip().upper()
    if not TABLE_NUM_REGEX.match(table_clean):
        return Response({'error': 'Invalid table format.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        table = RestaurantTable.objects.get(table_number=table_clean)
    except RestaurantTable.DoesNotExist:
        return Response({'error': 'Table not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not table.active:
        return Response({'error': 'Table is currently unavailable.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = RestaurantTableSerializer(table)
    return Response(serializer.data)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def check_table_session_status(request, table_number):
    """
    Validate whether a given session token is active at this physical table.
    If no valid active session token is provided, returns is_active_session=False and status=AVAILABLE.
    """
    table_clean = table_number.strip().upper()
    if not TABLE_NUM_REGEX.match(table_clean):
        return Response({'error': 'Invalid table format.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        table = RestaurantTable.objects.get(table_number=table_clean)
    except RestaurantTable.DoesNotExist:
        return Response({'error': 'Table not found.'}, status=status.HTTP_404_NOT_FOUND)

    session_token = request.GET.get('session_id') or request.GET.get('session_token')
    if not session_token:
        return Response({
            'table_id': table.table_number,
            'table_number': table.table_number,
            'display_number': table.display_number,
            'is_active_session': False,
            'has_active_session': False,
            'status': 'AVAILABLE',
            'message': 'No active session token provided. Fresh check-in required.'
        })

    try:
        session = CustomerSession.objects.get(
            session_id=session_token.strip(),
            table=table,
            status=CustomerSession.SessionStatus.ACTIVE,
            active=True
        )
    except (CustomerSession.DoesNotExist, ValueError):
        return Response({
            'table_id': table.table_number,
            'table_number': table.table_number,
            'display_number': table.display_number,
            'is_active_session': False,
            'has_active_session': False,
            'status': 'AVAILABLE',
            'message': 'Session is closed or invalid. Ready for new customer check-in.'
        })

    # Check for active ongoing orders for this session
    active_orders = table.orders.filter(
        customer_session=session
    ).exclude(
        order_status__in=['COMPLETED', 'CANCELLED']
    )

    if active_orders.exists():
        latest = active_orders.first()
        return Response({
            'table_id': table.table_number,
            'table_number': table.table_number,
            'display_number': table.display_number,
            'session_id': str(session.session_id),
            'is_active_session': True,
            'has_active_session': True,
            'status': 'ACTIVE',
            'customer_name': session.customer_name,
            'active_order_number': latest.order_number,
            'order_status': latest.order_status,
            'order_status_display': latest.get_order_status_display(),
            'payment_status': latest.payment_status,
        })
    else:
        return Response({
            'table_id': table.table_number,
            'table_number': table.table_number,
            'display_number': table.display_number,
            'session_id': str(session.session_id),
            'is_active_session': True,
            'has_active_session': True,
            'status': 'ACTIVE',
            'customer_name': session.customer_name,
            'active_order_number': None,
            'order_status': None,
        })


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@rate_limit(limit=15, window=60, key_prefix='checkin')
def customer_checkin(request):
    """
    Register a new customer dining session for a table.
    Creates a new TableSession with rate limiting and input validation.
    """
    serializer = CustomerCheckInSerializer(data=request.data)
    if not serializer.is_valid():
        error_msgs = []
        for field, errs in serializer.errors.items():
            if isinstance(errs, list):
                error_msgs.append(f"{errs[0]}")
            else:
                error_msgs.append(f"{field}: {errs}")
        error_str = " ".join(error_msgs) if error_msgs else "Invalid customer details."
        return Response({'error': error_str, 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    table_num = serializer.validated_data['table_number'].upper()
    try:
        table = RestaurantTable.objects.get(table_number=table_num)
    except RestaurantTable.DoesNotExist:
        return Response({'error': f'Table {table_num} not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not table.active:
        return Response({'error': f'Table {table_num} is currently unavailable.'}, status=status.HTTP_400_BAD_REQUEST)

    # Close any lingering previous sessions on this table that have no active orders
    old_sessions = table.customer_sessions.filter(active=True)
    for old_s in old_sessions:
        has_pending = old_s.orders.exclude(order_status__in=['COMPLETED', 'CANCELLED']).exists()
        if not has_pending:
            old_s.close()

    # Create new fresh session
    customer_session = CustomerSession.objects.create(
        table=table,
        customer_name=serializer.validated_data['customer_name'],
        customer_phone=serializer.validated_data['customer_phone'],
        status=CustomerSession.SessionStatus.ACTIVE,
        active=True,
        started_at=timezone.now()
    )

    return Response({
        'session_id': str(customer_session.session_id),
        'session_token': str(customer_session.session_id),
        'table_id': table.table_number,
        'table_number': table.table_number,
        'display_number': table.display_number,
        'customer_name': customer_session.customer_name,
        'status': customer_session.status,
        'message': f"Welcome {customer_session.customer_name}! Session created for Table {table.table_number}."
    }, status=status.HTTP_201_CREATED)

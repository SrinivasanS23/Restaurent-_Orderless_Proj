"""Domain services for order creation, calculation, and kitchen status management."""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Order, OrderItem
from menu.models import MenuItem
from tables.models import RestaurantTable, CustomerSession

logger = logging.getLogger('orders')


class OrderService:
    """Service handling order lifecycle, calculations, and kitchen status."""

    @staticmethod
    @transaction.atomic
    def create_order(table_number, items_data, customer_session_id=None, special_instructions='', idempotency_key=None):
        """
        Create a new dine-in order with item snapshots, GST calculations, and idempotency protection.
        """
        clean_table_num = str(table_number).strip().upper()
        clean_idempotency = str(idempotency_key).strip()[:64] if idempotency_key else ''

        # Idempotency check: if customer retry happened, return existing order
        if clean_idempotency:
            existing = Order.objects.filter(idempotency_key=clean_idempotency).first()
            if existing:
                logger.info(f"[IDEMPOTENT_ORDER_RETURN] Order='{existing.order_number}' Key='{clean_idempotency}'")
                return existing

        try:
            table = RestaurantTable.objects.select_for_update().get(table_number=clean_table_num)
        except RestaurantTable.DoesNotExist:
            raise ValueError(f"Table '{table_number}' does not exist.")

        if not table.active:
            raise ValueError("Table is currently unavailable.")

        if not items_data:
            raise ValueError("Order must contain at least one item.")

        # Find and validate customer session
        customer_session = None
        if customer_session_id:
            try:
                customer_session = CustomerSession.objects.get(
                    session_id=customer_session_id,
                    table=table,
                    status=CustomerSession.SessionStatus.ACTIVE,
                    active=True
                )
            except (CustomerSession.DoesNotExist, ValueError):
                raise ValueError("Your table session has ended or is invalid. Please start a fresh check-in.")
        else:
            raise ValueError("Customer check-in is required before placing an order.")

        # Validate menu items
        menu_item_ids = [int(item['menu_item_id']) for item in items_data]
        menu_items = MenuItem.objects.filter(id__in=menu_item_ids)
        menu_items_dict = {mi.id: mi for mi in menu_items}

        for item_data in items_data:
            mid = int(item_data['menu_item_id'])
            if mid not in menu_items_dict:
                raise ValueError(f"Menu item {mid} not found.")
            if not menu_items_dict[mid].available:
                raise ValueError(f"'{menu_items_dict[mid].name}' is currently unavailable.")
            if int(item_data.get('quantity', 0)) < 1:
                raise ValueError("Quantity must be at least 1.")

        # Sanitize special instructions against XSS
        clean_instructions = escape(special_instructions.strip())[:300] if special_instructions else ''

        order = Order.objects.create(
            table=table,
            customer_session=customer_session,
            idempotency_key=clean_idempotency,
            payment_status=Order.PaymentStatus.PENDING,
            order_status=Order.OrderStatus.ORDER_CREATED,
            special_instructions=clean_instructions
        )

        # Create OrderItems with name snapshots
        for item_data in items_data:
            menu_item = menu_items_dict[int(item_data['menu_item_id'])]
            quantity = int(item_data['quantity'])
            unit_price = menu_item.price
            subtotal = unit_price * quantity
            raw_item_notes = item_data.get('special_instructions', '')
            clean_item_notes = escape(raw_item_notes.strip())[:150] if raw_item_notes else ''

            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                item_name_snapshot=menu_item.name,
                quantity=quantity,
                unit_price=unit_price,
                subtotal=subtotal,
                special_instructions=clean_item_notes
            )

        # Calculate GST and grand total
        order.calculate_totals()
        order.save()

        # Notify kitchen and customer via WebSocket
        OrderService._notify_kitchen_new_order(order)
        OrderService._notify_customer_order_update(order)

        try:
            from utils.cloud_db import sync_order_to_cloud
            sync_order_to_cloud(order)
        except Exception:
            pass

        return order

    @staticmethod
    @transaction.atomic
    def update_order_status(order_id, new_status, user=None):
        """
        Update kitchen order status with atomic concurrency protection and idempotency.
        ONE-CLICK state transitions:
        - ORDER_CREATED -> PREPARING (Accept Order)
        - PREPARING -> READY (Mark Ready)
        - READY -> SERVED (Mark Served)
        """
        try:
            # Query with select_for_update to serialize concurrent transitions
            if isinstance(order_id, str) and order_id.startswith('ORD-'):
                order = Order.objects.select_for_update().get(order_number=order_id.strip().upper())
            else:
                order = Order.objects.select_for_update().get(id=int(order_id))
        except (Order.DoesNotExist, ValueError):
            raise ValueError("Order not found.")

        # Idempotency check: if order is already in target status, return cleanly
        if order.order_status == new_status:
            return order

        if not order.can_transition_to(new_status):
            raise ValueError(
                f"Cannot transition order #{order.order_number} from {order.get_order_status_display()} to {new_status}."
            )

        order.order_status = new_status
        if new_status == Order.OrderStatus.SERVED:
            order.served_at = timezone.now()
        elif new_status == Order.OrderStatus.COMPLETED:
            order.completed_at = timezone.now()
        order.save()

        # Notify via WebSocket
        OrderService._notify_order_update(order)

        try:
            from utils.cloud_db import sync_order_to_cloud
            sync_order_to_cloud(order)
        except Exception:
            pass

        return order

    @staticmethod
    def _notify_kitchen_new_order(order):
        """Send new order event to kitchen WebSocket group."""
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                order_data = OrderService._serialize_order(order)
                async_to_sync(channel_layer.group_send)(
                    'kitchen',
                    {
                        'type': 'kitchen_new_order',
                        'order': order_data
                    }
                )
        except Exception as e:
            logger.debug(f"WS notify kitchen error: {e}")

    @staticmethod
    def _notify_order_update(order):
        """Send order status update to both kitchen and customer WebSocket groups."""
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                order_data = OrderService._serialize_order(order)

                # Notify kitchen
                async_to_sync(channel_layer.group_send)(
                    'kitchen',
                    {
                        'type': 'kitchen_order_update',
                        'order': order_data
                    }
                )

                # Notify customer
                OrderService._notify_customer_order_update(order)
        except Exception as e:
            logger.debug(f"WS notify update error: {e}")

    @staticmethod
    def _notify_customer_order_update(order):
        """Send update specifically to the customer tracking room."""
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                order_data = OrderService._serialize_order(order)
                async_to_sync(channel_layer.group_send)(
                    f'order_{order.order_number}',
                    {
                        'type': 'order_status_update',
                        'order': order_data
                    }
                )
        except Exception as e:
            logger.debug(f"WS notify customer error: {e}")

    @staticmethod
    def _serialize_order(order):
        """Serialize order data for WebSocket & REST."""
        items = []
        for item in order.items.select_related('menu_item').all():
            items.append({
                'id': item.id,
                'name': item.name,
                'item_name_snapshot': item.item_name_snapshot,
                'quantity': item.quantity,
                'unit_price': str(item.unit_price),
                'subtotal': str(item.subtotal),
                'special_instructions': item.special_instructions,
                'emoji': item.menu_item.emoji if item.menu_item else '',
            })

        session_status = 'CLOSED'
        if order.customer_session:
            session_status = order.customer_session.status

        return {
            'id': order.id,
            'order_number': order.order_number,
            'table_number': order.table.table_number,
            'table_display': order.table.display_number,
            'customer_name': order.customer_name_display,
            'customer_phone_masked': order.customer_phone_masked,
            'order_status': order.order_status,
            'order_status_display': order.get_order_status_display(),
            'payment_status': order.payment_status,
            'payment_status_display': order.get_payment_status_display(),
            'payment_method': order.payment_method,
            'session_status': session_status,
            'subtotal': str(order.subtotal),
            'discount': str(order.discount),
            'taxable_amount': str(order.taxable_amount),
            'cgst_amount': str(order.cgst_amount),
            'sgst_amount': str(order.sgst_amount),
            'tax_amount': str(order.tax_amount),
            'total_amount': str(order.total_amount),
            'special_instructions': order.special_instructions,
            'items': items,
            'created_at': order.created_at.isoformat() if order.created_at else None,
            'updated_at': order.updated_at.isoformat() if order.updated_at else None,
            'served_at': order.served_at.isoformat() if order.served_at else None,
            'paid_at': order.paid_at.isoformat() if order.paid_at else None,
            'completed_at': order.completed_at.isoformat() if order.completed_at else None,
        }

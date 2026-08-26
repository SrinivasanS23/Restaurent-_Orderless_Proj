"""Unit and integration tests for orders app and dining sessions."""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from tables.models import RestaurantTable, CustomerSession
from menu.models import MenuCategory, MenuItem
from orders.models import Order, OrderItem
from orders.services import OrderService


class OrderTests(TestCase):
    def setUp(self):
        self.table = RestaurantTable.objects.create(table_number='T05', active=True)
        self.inactive_table = RestaurantTable.objects.create(table_number='T12', active=False)
        self.session = CustomerSession.objects.create(
            table=self.table, customer_name='Test Customer A', customer_phone='+919876543210',
            status=CustomerSession.SessionStatus.ACTIVE, active=True
        )
        self.cat = MenuCategory.objects.create(name='Fast Food', icon='🍔')
        self.item1 = MenuItem.objects.create(category=self.cat, name='Burger', price=Decimal('180.00'), available=True)
        self.item2 = MenuItem.objects.create(category=self.cat, name='Fries', price=Decimal('120.00'), available=True)
        self.item_unavail = MenuItem.objects.create(category=self.cat, name='Shake', price=Decimal('90.00'), available=False)
        self.staff_user = User.objects.create_user('staff', 'staff@test.com', 'pass123', is_staff=True)

    def test_order_creation_calculates_gst_correctly(self):
        # 2x 180 + 1x 120 = 480 subtotal. GST 5% = 24.00 (CGST 12 + SGST 12). Grand Total = 504.00
        order = OrderService.create_order(
            table_number='T05',
            items_data=[
                {'menu_item_id': self.item1.id, 'quantity': 2},
                {'menu_item_id': self.item2.id, 'quantity': 1}
            ],
            customer_session_id=str(self.session.session_id)
        )

        self.assertEqual(order.subtotal, Decimal('480.00'))
        self.assertEqual(order.cgst_amount, Decimal('12.00'))
        self.assertEqual(order.sgst_amount, Decimal('12.00'))
        self.assertEqual(order.tax_amount, Decimal('24.00'))
        self.assertEqual(order.total_amount, Decimal('504.00'))
        self.assertEqual(order.customer_session, self.session)
        self.assertEqual(order.order_status, Order.OrderStatus.ORDER_CREATED)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)

    def test_reject_order_on_closed_session(self):
        self.session.close()
        with self.assertRaises(ValueError) as ctx:
            OrderService.create_order(
                table_number='T05',
                items_data=[{'menu_item_id': self.item1.id, 'quantity': 1}],
                customer_session_id=str(self.session.session_id)
            )
        self.assertIn('ended', str(ctx.exception).lower())

    def test_reject_order_without_customer_session(self):
        with self.assertRaises(ValueError) as ctx:
            OrderService.create_order(
                table_number='T05',
                items_data=[{'menu_item_id': self.item1.id, 'quantity': 1}],
                customer_session_id=None
            )
        self.assertIn('required', str(ctx.exception).lower())

    def test_item_name_snapshot_preservation(self):
        order = OrderService.create_order(
            table_number='T05',
            items_data=[{'menu_item_id': self.item1.id, 'quantity': 1}],
            customer_session_id=str(self.session.session_id)
        )
        item = order.items.first()
        self.assertEqual(item.item_name_snapshot, 'Burger')

        self.item1.name = 'Super Deluxe Burger'
        self.item1.price = Decimal('300.00')
        self.item1.save()

        item.refresh_from_db()
        self.assertEqual(item.name, 'Burger')
        self.assertEqual(item.unit_price, Decimal('180.00'))

    def test_cannot_order_on_inactive_table(self):
        with self.assertRaises(ValueError):
            OrderService.create_order('T12', [{'menu_item_id': self.item1.id, 'quantity': 1}], customer_session_id=str(self.session.session_id))

    def test_cannot_order_unavailable_item(self):
        with self.assertRaises(ValueError):
            OrderService.create_order('T05', [{'menu_item_id': self.item_unavail.id, 'quantity': 1}], customer_session_id=str(self.session.session_id))

    def test_order_status_state_machine(self):
        order = OrderService.create_order('T05', [{'menu_item_id': self.item1.id, 'quantity': 1}], customer_session_id=str(self.session.session_id))

        order = OrderService.update_order_status(order.id, 'ACCEPTED')
        self.assertEqual(order.order_status, 'ACCEPTED')

        order = OrderService.update_order_status(order.id, 'PREPARING')
        self.assertEqual(order.order_status, 'PREPARING')

        order = OrderService.update_order_status(order.id, 'READY')
        self.assertEqual(order.order_status, 'READY')

        order = OrderService.update_order_status(order.id, 'SERVED')
        self.assertEqual(order.order_status, 'SERVED')
        self.assertIsNotNone(order.served_at)

        with self.assertRaises(ValueError):
            OrderService.update_order_status(order.id, 'PREPARING')

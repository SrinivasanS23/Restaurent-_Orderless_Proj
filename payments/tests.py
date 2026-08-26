"""Unit and integration tests for payments and receipts."""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from tables.models import RestaurantTable, CustomerSession
from menu.models import MenuCategory, MenuItem
from orders.models import Order
from orders.services import OrderService
from payments.models import Payment, Receipt
from payments.services import PaymentService
from payments.receipt_service import ReceiptService


class PaymentTests(TestCase):
    def setUp(self):
        self.table = RestaurantTable.objects.create(table_number='T08', active=True)
        self.session = CustomerSession.objects.create(
            table=self.table, customer_name='Srinivasan', customer_phone='+919876543210'
        )
        self.cat = MenuCategory.objects.create(name='Drinks', icon='🥤')
        self.item = MenuItem.objects.create(category=self.cat, name='Fresh Juice', price=Decimal('100.00'), available=True)
        self.staff_user = User.objects.create_user('cashier', 'cashier@test.com', 'pass123', is_staff=True)

    def test_cannot_pay_desk_before_served(self):
        order = OrderService.create_order(
            table_number='T08',
            items_data=[{'menu_item_id': self.item.id, 'quantity': 1}],
            customer_session_id=str(self.session.session_id)
        )
        with self.assertRaises(ValueError) as ctx:
            PaymentService.process_desk_payment(order.order_number, 'CASH', order.total_amount, cashier=self.staff_user)
        self.assertIn('served', str(ctx.exception).lower())

    def test_successful_desk_payment_with_cash_change_and_pdf_receipt(self):
        order = OrderService.create_order(
            table_number='T08',
            items_data=[{'menu_item_id': self.item.id, 'quantity': 2}], # 200 + 10 GST = 210
            customer_session_id=str(self.session.session_id)
        )
        OrderService.update_order_status(order.id, 'ACCEPTED')
        OrderService.update_order_status(order.id, 'PREPARING')
        OrderService.update_order_status(order.id, 'READY')
        OrderService.update_order_status(order.id, 'SERVED')

        res = PaymentService.process_desk_payment(
            order_number=order.order_number,
            payment_method='CASH',
            amount=order.total_amount,
            cashier=self.staff_user,
            cash_received=Decimal('500.00'),
            reference='CASH-POS-1'
        )

        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(order.order_status, Order.OrderStatus.COMPLETED)
        self.assertEqual(order.payment_method, 'CASH')
        self.assertEqual(res['cash_change'], '290.00')
        self.assertTrue(Receipt.objects.filter(order=order).exists())

    def test_prevent_duplicate_payment(self):
        order = OrderService.create_order(
            table_number='T08',
            items_data=[{'menu_item_id': self.item.id, 'quantity': 1}],
            customer_session_id=str(self.session.session_id)
        )
        OrderService.update_order_status(order.id, 'ACCEPTED')
        OrderService.update_order_status(order.id, 'PREPARING')
        OrderService.update_order_status(order.id, 'READY')
        OrderService.update_order_status(order.id, 'SERVED')

        PaymentService.process_desk_payment(order.order_number, 'UPI', order.total_amount)

        with self.assertRaises(ValueError) as ctx:
            PaymentService.process_desk_payment(order.order_number, 'UPI', order.total_amount)
        self.assertIn('already', str(ctx.exception).lower())

    def test_pdf_receipt_download_api(self):
        order = OrderService.create_order(
            table_number='T08',
            items_data=[{'menu_item_id': self.item.id, 'quantity': 1}],
            customer_session_id=str(self.session.session_id)
        )
        ReceiptService.generate_pdf_receipt(order)

        # Authenticated with session ID header
        response = self.client.get(
            f"/api/orders/{order.order_number}/receipt/pdf/",
            HTTP_X_SESSION_ID=str(self.session.session_id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

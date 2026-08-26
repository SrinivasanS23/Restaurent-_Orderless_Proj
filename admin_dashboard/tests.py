"""Unit and integration tests for Admin Operations Dashboard features."""
from decimal import Decimal
from datetime import datetime, time
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from tables.models import RestaurantTable, CustomerSession
from menu.models import MenuCategory, MenuItem
from orders.models import Order, OrderItem
from orders.services import OrderService
from payments.models import Payment
from payments.services import PaymentService


class AdminDashboardFeatureTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user('adminstaff', 'admin@test.com', 'AdminPass123!', is_staff=True)
        self.client.force_login(self.staff_user)

        self.table = RestaurantTable.objects.create(table_number='T01', active=True)
        self.session = CustomerSession.objects.create(
            table=self.table, customer_name='Alice Wonderland', customer_phone='+919876543210',
            status=CustomerSession.SessionStatus.ACTIVE, active=True
        )

        self.cat = MenuCategory.objects.create(name='Snacks', icon='🥪', display_order=1)
        self.item = MenuItem.objects.create(
            category=self.cat, name='Club Sandwich', price=Decimal('180.00'), emoji='🥪',
            is_vegetarian=True, is_bestseller=True, available=True
        )

        # Place & complete order
        self.order = OrderService.create_order(
            table_number='T01',
            items_data=[{'menu_item_id': self.item.id, 'quantity': 2}], # 360 + 18 GST = 378
            customer_session_id=str(self.session.session_id)
        )
        OrderService.update_order_status(self.order.id, 'ACCEPTED')
        OrderService.update_order_status(self.order.id, 'PREPARING')
        OrderService.update_order_status(self.order.id, 'READY')
        OrderService.update_order_status(self.order.id, 'SERVED')
        PaymentService.process_desk_payment(self.order.order_number, 'UPI', self.order.total_amount, cashier=self.staff_user)

    # 1. STATS METRICS (MONTHLY & YEARLY REVENUE)
    def test_stats_api_includes_monthly_and_yearly_revenue(self):
        res = self.client.get('/dashboard/api/stats/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('today_sales', data)
        self.assertIn('month_sales', data)
        self.assertIn('year_sales', data)
        self.assertEqual(Decimal(data['month_sales']), Decimal('378.00'))
        self.assertEqual(Decimal(data['year_sales']), Decimal('378.00'))

    # 2. CSV EXPORT TESTS
    def test_export_orders_csv(self):
        res = self.client.get('/dashboard/api/export/orders/csv/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="OrderLess_Orders_', res['Content-Disposition'])
        content = res.content.decode('utf-8')
        self.assertIn('Order Number,Table,Customer Name', content)
        self.assertIn(self.order.order_number, content)
        self.assertIn('Alice Wonderland', content)

    def test_export_customers_csv(self):
        res = self.client.get('/dashboard/api/export/customers/csv/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="OrderLess_Customers_', res['Content-Disposition'])
        content = res.content.decode('utf-8')
        self.assertIn('Customer Name,Phone Number', content)
        self.assertIn('Alice Wonderland', content)

    # 3. "SORT BY DATE" / CALENDAR FILTER
    def test_orders_list_date_filter(self):
        today_str = timezone.now().strftime('%Y-%m-%d')
        res = self.client.get(f'/dashboard/api/orders/?date={today_str}')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['orders'][0]['order_number'], self.order.order_number)

        # Future/past date with no orders
        res_empty = self.client.get('/dashboard/api/orders/?date=2020-01-01')
        self.assertEqual(res_empty.status_code, 200)
        self.assertEqual(res_empty.json()['total'], 0)

    # 4. MENU ITEMS CRUD (ADD & EDIT ITEMS)
    def test_menu_items_list_api(self):
        res = self.client.get('/dashboard/api/menu/items/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(len(data) >= 1)
        self.assertEqual(data[0]['name'], 'Club Sandwich')

    def test_add_new_menu_item(self):
        res = self.client.post('/dashboard/api/menu/items/', {
            'name': 'Cold Coffee',
            'category': self.cat.id,
            'price': '120.00',
            'emoji': '🧋',
            'description': 'Refreshing cold coffee with ice cream',
            'is_vegetarian': True,
            'is_bestseller': False,
            'available': True
        }, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data['item']['name'], 'Cold Coffee')
        self.assertEqual(Decimal(data['item']['price']), Decimal('120.00'))
        self.assertTrue(MenuItem.objects.filter(name='Cold Coffee').exists())

    def test_edit_menu_item(self):
        res = self.client.patch(f'/dashboard/api/menu/items/{self.item.id}/', {
            'name': 'Grilled Club Sandwich Deluxe',
            'price': '220.00',
            'available': False
        }, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, 'Grilled Club Sandwich Deluxe')
        self.assertEqual(self.item.price, Decimal('220.00'))
        self.assertFalse(self.item.available)

    def test_delete_menu_item(self):
        item_to_delete = MenuItem.objects.create(
            category=self.cat, name='Temporary Dish', price=Decimal('99.00')
        )
        res = self.client.delete(f'/dashboard/api/menu/items/{item_to_delete.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(MenuItem.objects.filter(id=item_to_delete.id).exists())

    def test_menu_categories_api(self):
        res = self.client.get('/dashboard/api/menu/categories/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(len(data) >= 1)
        self.assertEqual(data[0]['name'], 'Snacks')

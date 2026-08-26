"""Unit and integration tests for tables and customer dining sessions."""
from django.test import TestCase
from tables.models import RestaurantTable, CustomerSession
from orders.models import Order
from menu.models import MenuCategory, MenuItem


class TableAndSessionTests(TestCase):
    def setUp(self):
        self.table = RestaurantTable.objects.create(table_number='T05', active=True)
        self.inactive_table = RestaurantTable.objects.create(table_number='T12', active=False)

    def test_table_display_number(self):
        self.assertEqual(self.table.display_number, '05')

    def test_get_active_table_api_never_exposes_customer(self):
        res = self.client.get('/api/tables/T05/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['table_id'], 'T05')
        self.assertEqual(data['status'], 'AVAILABLE')
        self.assertNotIn('customer_name', data)
        self.assertNotIn('customer_phone', data)

    def test_get_inactive_table_api(self):
        res = self.client.get('/api/tables/T12/')
        self.assertEqual(res.status_code, 400)

    def test_customer_checkin_success_creates_unique_active_session(self):
        res = self.client.post('/api/table-sessions/', {
            'table_id': 'T05',
            'customer_name': 'Test Customer A',
            'customer_phone': '9876543210'
        }, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data['customer_name'], 'Test Customer A')
        self.assertEqual(data['status'], 'ACTIVE')
        self.assertIn('session_id', data)

        session = CustomerSession.objects.get(session_id=data['session_id'])
        self.assertEqual(session.status, CustomerSession.SessionStatus.ACTIVE)
        self.assertTrue(session.active)

    def test_customer_checkin_short_name_rejected(self):
        res = self.client.post('/api/table-sessions/', {
            'table_id': 'T05',
            'customer_name': 'A',
            'customer_phone': '9876543210'
        }, content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_customer_checkin_invalid_phone_rejected(self):
        res = self.client.post('/api/table-sessions/', {
            'table_id': 'T05',
            'customer_name': 'Siva',
            'customer_phone': '123'
        }, content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_session_status_for_new_visitor_without_token(self):
        res = self.client.get('/api/tables/T05/session-status/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['is_active_session'], False)
        self.assertEqual(data['status'], 'AVAILABLE')

    def test_session_status_for_closed_session(self):
        session = CustomerSession.objects.create(
            table=self.table, customer_name='Old Customer', customer_phone='+919876543210',
            status=CustomerSession.SessionStatus.CLOSED, active=False
        )
        res = self.client.get(f'/api/tables/T05/session-status/?session_id={session.session_id}')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['is_active_session'], False)
        self.assertEqual(data['status'], 'AVAILABLE')

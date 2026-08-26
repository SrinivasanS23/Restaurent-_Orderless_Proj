"""
Comprehensive Automated Security Test Suite for OrderLess Application.
Tests:
1. Password hashing algorithm strength.
2. Session & CSRF cookie security flags.
3. Login rate limiting and brute-force account lockout.
4. Insecure Direct Object Reference (IDOR) defense.
5. Role-based authorization & staff permissions.
6. Input validation and path traversal defense.
7. Security headers and Content-Security-Policy (CSP).
8. Endpoint abuse protection & rate limiting.
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password, identify_hasher
from django.core.cache import cache
from django.conf import settings

from tables.models import RestaurantTable, CustomerSession
from menu.models import MenuCategory, MenuItem
from orders.models import Order, OrderItem
from orders.services import OrderService
from security.rate_limit import RateLimiter, clear_failed_logins, MAX_LOGIN_ATTEMPTS


class SecurityHardeningTests(TestCase):

    def setUp(self):
        cache.clear()
        self.client = Client()
        
        # Test physical tables
        self.table = RestaurantTable.objects.create(table_number='T05', active=True)
        self.other_table = RestaurantTable.objects.create(table_number='T02', active=True)
        
        # Test Customer Sessions
        self.session_a = CustomerSession.objects.create(
            table=self.table, customer_name='Customer A', customer_phone='+919876543210',
            status=CustomerSession.SessionStatus.ACTIVE, active=True
        )
        self.session_b = CustomerSession.objects.create(
            table=self.other_table, customer_name='Customer B', customer_phone='+919123456780',
            status=CustomerSession.SessionStatus.ACTIVE, active=True
        )
        
        # Test Menu Items
        self.cat = MenuCategory.objects.create(name='Drinks', icon='🥤')
        self.item = MenuItem.objects.create(category=self.cat, name='Iced Latte', price=Decimal('150.00'), available=True)
        
        # Staff & Regular Users
        self.staff_user = User.objects.create_user('staffuser', 'staff@test.com', 'SecureStaffPass123!', is_staff=True)
        self.regular_user = User.objects.create_user('regularuser', 'user@test.com', 'SecureUserPass123!', is_staff=False)
        
        # Create Order for Customer A
        self.order_a = OrderService.create_order(
            table_number='T05',
            items_data=[{'menu_item_id': self.item.id, 'quantity': 1}],
            customer_session_id=str(self.session_a.session_id)
        )

    def tearDown(self):
        cache.clear()

    # =====================================================================
    # 1. PASSWORD HASHING STRENGTH
    # =====================================================================
    def test_password_hashing_uses_strong_algorithm(self):
        user = User.objects.create_user('hashtest', 'hash@test.com', 'TestSecurePass2026!')
        hasher = identify_hasher(user.password)
        self.assertIn(hasher.algorithm, ['argon2', 'pbkdf2_sha256'])
        self.assertTrue(check_password('TestSecurePass2026!', user.password))

    # =====================================================================
    # 2. SESSION & COOKIE SECURITY
    # =====================================================================
    def test_session_cookie_settings_are_hardened(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 28800)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, 'Lax')

    # =====================================================================
    # 3. LOGIN RATE LIMITING & BRUTE FORCE LOCKOUT
    # =====================================================================
    def test_login_brute_force_lockout_after_max_attempts(self):
        clear_failed_logins(None, 'staffuser')
        
        # Perform MAX_LOGIN_ATTEMPTS failed logins
        for i in range(MAX_LOGIN_ATTEMPTS):
            res = self.client.post('/login/', {
                'username': 'staffuser',
                'password': 'WrongPassword123!'
            })
            self.assertIn(res.status_code, [401, 429])

        # 6th attempt must be strictly locked out with HTTP 429
        locked_res = self.client.post('/login/', {
            'username': 'staffuser',
            'password': 'WrongPassword123!'
        })
        self.assertEqual(locked_res.status_code, 429)
        self.assertContains(locked_res, "locked", status_code=429)

    def test_successful_login_clears_failed_attempts(self):
        clear_failed_logins(None, 'staffuser')
        
        # 2 failed attempts
        for _ in range(2):
            self.client.post('/login/', {'username': 'staffuser', 'password': 'WrongPassword!'})

        # Successful login
        success_res = self.client.post('/login/', {
            'username': 'staffuser',
            'password': 'SecureStaffPass123!'
        })
        self.assertEqual(success_res.status_code, 302)

    # =====================================================================
    # 4. IDOR (INSECURE DIRECT OBJECT REFERENCE) DEFENSE
    # =====================================================================
    def test_idor_blocked_unauthenticated_request_without_session_token(self):
        res = self.client.get(f'/api/orders/{self.order_a.order_number}/')
        self.assertEqual(res.status_code, 403)
        self.assertIn('denied', res.json()['error'].lower())

    def test_idor_blocked_mismatched_session_token(self):
        res = self.client.get(
            f'/api/orders/{self.order_a.order_number}/',
            HTTP_X_SESSION_ID=str(self.session_b.session_id)
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn('denied', res.json()['error'].lower())

    def test_idor_allowed_matching_session_token(self):
        res = self.client.get(
            f'/api/orders/{self.order_a.order_number}/',
            HTTP_X_SESSION_ID=str(self.session_a.session_id)
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['order_number'], self.order_a.order_number)

    def test_idor_allowed_authenticated_staff(self):
        self.client.force_login(self.staff_user)
        res = self.client.get(f'/api/orders/{self.order_a.order_number}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['order_number'], self.order_a.order_number)

    def test_idor_blocked_on_order_receipt(self):
        # Mismatched session on receipt endpoint
        res = self.client.get(
            f'/api/orders/{self.order_a.order_number}/receipt/',
            HTTP_X_SESSION_ID=str(self.session_b.session_id)
        )
        self.assertEqual(res.status_code, 403)

    # =====================================================================
    # 5. STAFF PERMISSION ENFORCEMENT
    # =====================================================================
    def test_kitchen_orders_blocked_for_unauthenticated_and_regular_users(self):
        # Unauthenticated
        res1 = self.client.get('/api/orders/kitchen/')
        self.assertEqual(res1.status_code, 403)

        # Regular non-staff user
        self.client.force_login(self.regular_user)
        res2 = self.client.get('/api/orders/kitchen/')
        self.assertEqual(res2.status_code, 403)

    def test_payment_desk_blocked_for_non_staff(self):
        res = self.client.post('/api/payments/desk/', {
            'order_number': self.order_a.order_number,
            'payment_method': 'CASH',
            'amount': '157.50'
        }, content_type='application/json')
        self.assertEqual(res.status_code, 403)

    def test_admin_dashboard_api_blocked_for_non_staff(self):
        res = self.client.get('/dashboard/api/stats/')
        self.assertEqual(res.status_code, 403)

    # =====================================================================
    # 6. INPUT VALIDATION & PATH TRAVERSAL DEFENSE
    # =====================================================================
    def test_invalid_order_number_format_rejected(self):
        res = self.client.get('/api/orders/INVALID-FORMAT!/')
        self.assertEqual(res.status_code, 400)

    def test_invalid_table_format_rejected(self):
        res = self.client.get('/api/tables/TABLE-999999/')
        self.assertEqual(res.status_code, 400)

    def test_xss_special_instructions_sanitization(self):
        payload = "<script>alert('XSS')</script> Extra cheese"
        order = OrderService.create_order(
            table_number='T05',
            items_data=[{'menu_item_id': self.item.id, 'quantity': 1}],
            customer_session_id=str(self.session_a.session_id),
            special_instructions=payload
        )
        self.assertNotIn("<script>", order.special_instructions)
        self.assertIn("&lt;script&gt;", order.special_instructions)

    # =====================================================================
    # 7. SECURITY HEADERS & CONTENT SECURITY POLICY (CSP)
    # =====================================================================
    def test_security_headers_present_on_http_response(self):
        res = self.client.get('/api/tables/T05/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(res['X-Frame-Options'], 'DENY')
        self.assertEqual(res['Referrer-Policy'], 'strict-origin-when-cross-origin')
        self.assertIn("default-src 'self'", res['Content-Security-Policy'])

    # =====================================================================
    # 8. RATE LIMITING ON PUBLIC CHECK-IN
    # =====================================================================
    def test_customer_checkin_rate_limiting(self):
        cache.clear()
        # Rate limit is 15 requests/min on check-in
        for i in range(15):
            r = self.client.post('/api/table-sessions/', {
                'table_id': 'T05',
                'customer_name': f"Guest {i}",
                'customer_phone': '9876543210'
            }, content_type='application/json')
            self.assertEqual(r.status_code, 201)

        # 16th request must be throttled with HTTP 429
        throttled_res = self.client.post('/api/table-sessions/', {
            'table_id': 'T05',
            'customer_name': "Guest Exceeded",
            'customer_phone': '9876543210'
        }, content_type='application/json')
        self.assertEqual(throttled_res.status_code, 429)
        self.assertIn('Retry-After', throttled_res.headers)

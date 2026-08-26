"""Unit tests for menu app."""
from django.test import TestCase
from .models import MenuCategory, MenuItem


class MenuTests(TestCase):
    def setUp(self):
        self.cat = MenuCategory.objects.create(name='Main Course', icon='🍛', display_order=1)
        self.item1 = MenuItem.objects.create(
            category=self.cat, name='Burger', price=150.00, available=True
        )
        self.item2 = MenuItem.objects.create(
            category=self.cat, name='Special Pizza', price=300.00, available=False
        )

    def test_menu_list_api(self):
        response = self.client.get('/api/menu/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(len(data[0]['items']), 2)

    def test_categories_api(self):
        response = self.client.get('/api/menu/categories/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

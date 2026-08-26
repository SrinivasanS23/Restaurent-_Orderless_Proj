"""Models for restaurant menu."""
from django.db import models


class MenuCategory(models.Model):
    """A category of menu items (e.g. Starters, Main Course)."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    icon = models.CharField(max_length=10, blank=True, default='🍽️', help_text="Emoji icon for category")
    display_order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name_plural = 'Menu Categories'

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    """A single food/drink item on the menu."""
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='menu_images/', blank=True, null=True)
    emoji = models.CharField(max_length=10, blank=True, default='🍽️', help_text="Emoji fallback when no image")
    available = models.BooleanField(default=True)
    is_vegetarian = models.BooleanField(default=False)
    is_bestseller = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} - ₹{self.price}"

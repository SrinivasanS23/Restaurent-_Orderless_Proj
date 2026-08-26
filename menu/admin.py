"""Admin configuration for menu."""
from django.contrib import admin
from .models import MenuCategory, MenuItem


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'display_order', 'active', 'created_at')
    list_filter = ('active',)
    search_fields = ('name',)
    list_editable = ('display_order', 'active')


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'available', 'is_vegetarian', 'is_bestseller')
    list_filter = ('category', 'available', 'is_vegetarian', 'is_bestseller')
    search_fields = ('name', 'description')
    list_editable = ('price', 'available')

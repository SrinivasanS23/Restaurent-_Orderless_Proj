"""Serializers for menu."""
from rest_framework import serializers
from .models import MenuCategory, MenuItem


class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = MenuItem
        fields = [
            'id', 'name', 'description', 'price', 'image', 'image_url', 'emoji', 'is_deleted',
            'available', 'is_vegetarian', 'is_bestseller',
            'category', 'category_name'
        ]


class MenuCategorySerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = MenuCategory
        fields = ['id', 'name', 'icon', 'display_order', 'items']

    def get_items(self, obj):
        active_items = obj.items.filter(is_deleted=False)
        return MenuItemSerializer(active_items, many=True).data

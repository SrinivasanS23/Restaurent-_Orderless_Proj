"""Serializers for menu."""
from rest_framework import serializers
from .models import MenuCategory, MenuItem


class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = MenuItem
        fields = [
            'id', 'name', 'description', 'price', 'image', 'emoji',
            'available', 'is_vegetarian', 'is_bestseller',
            'category', 'category_name'
        ]


class MenuCategorySerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)

    class Meta:
        model = MenuCategory
        fields = ['id', 'name', 'icon', 'display_order', 'items']

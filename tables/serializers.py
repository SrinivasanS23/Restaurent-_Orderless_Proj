"""Serializers for tables and customer dining sessions."""
import re
from rest_framework import serializers
from .models import RestaurantTable, CustomerSession


class RestaurantTableSerializer(serializers.ModelSerializer):
    table_id = serializers.CharField(source='table_number', read_only=True)
    display_number = serializers.ReadOnlyField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = RestaurantTable
        fields = ['id', 'table_id', 'table_number', 'display_number', 'qr_token', 'active', 'status']

    def get_status(self, obj):
        has_active_order = obj.orders.exclude(
            order_status__in=['COMPLETED', 'CANCELLED']
        ).exists()
        return "OCCUPIED" if has_active_order else "AVAILABLE"


class CustomerSessionSerializer(serializers.ModelSerializer):
    table_number = serializers.CharField(source='table.table_number', read_only=True)
    table_id = serializers.CharField(source='table.table_number', read_only=True)
    masked_phone = serializers.ReadOnlyField()

    class Meta:
        model = CustomerSession
        fields = [
            'session_id', 'table_id', 'table_number',
            'customer_name', 'customer_phone', 'masked_phone',
            'status', 'active', 'started_at', 'ended_at', 'created_at'
        ]
        read_only_fields = ['session_id', 'status', 'active', 'started_at', 'ended_at', 'created_at']


class CustomerCheckInSerializer(serializers.Serializer):
    table_id = serializers.CharField(max_length=10, required=False)
    table_number = serializers.CharField(max_length=10, required=False)
    customer_name = serializers.CharField(max_length=100, min_length=2)
    customer_phone = serializers.CharField(max_length=20)

    def validate(self, attrs):
        table_key = attrs.get('table_id') or attrs.get('table_number')
        if not table_key:
            raise serializers.ValidationError("table_number or table_id is required.")
        attrs['table_number'] = table_key
        return attrs

    def validate_customer_name(self, value):
        name = value.strip()
        if len(name) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters.")
        return name

    def validate_customer_phone(self, value):
        cleaned = re.sub(r'[\s\-\(\)]', '', value)
        if re.match(r'^[6-9]\d{9}$', cleaned):
            return f"+91{cleaned}"
        elif re.match(r'^\+91[6-9]\d{9}$', cleaned):
            return cleaned
        elif re.match(r'^\+\d{10,15}$', cleaned):
            return cleaned
        elif len(cleaned) == 10 and cleaned.isdigit():
            return f"+91{cleaned}"
        else:
            raise serializers.ValidationError("Please enter a valid 10-digit mobile number.")

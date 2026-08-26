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
    name = serializers.CharField(max_length=100, required=False)
    customer_name = serializers.CharField(max_length=100, required=False)
    phone = serializers.CharField(max_length=20, required=False)
    customer_phone = serializers.CharField(max_length=20, required=False)

    def validate(self, attrs):
        # Resolve table
        table_key = attrs.get('table_number') or attrs.get('table_id')
        if not table_key:
            raise serializers.ValidationError({"table_number": "Table number is required."})
        attrs['table_number'] = str(table_key).strip().upper()

        # Resolve customer name
        raw_name = (attrs.get('customer_name') or attrs.get('name') or '').strip()
        if len(raw_name) < 2:
            raise serializers.ValidationError({"customer_name": "Please enter a valid name (at least 2 characters)."})
        attrs['customer_name'] = raw_name

        # Resolve customer phone
        raw_phone = (attrs.get('customer_phone') or attrs.get('phone') or '').strip()
        cleaned_phone = re.sub(r'[\s\-\(\)\.]', '', raw_phone)
        
        if re.match(r'^[6-9]\d{9}$', cleaned_phone):
            attrs['customer_phone'] = f"+91{cleaned_phone}"
        elif re.match(r'^\+91[6-9]\d{9}$', cleaned_phone):
            attrs['customer_phone'] = cleaned_phone
        elif len(cleaned_phone) == 10 and cleaned_phone.isdigit():
            attrs['customer_phone'] = f"+91{cleaned_phone}"
        elif re.match(r'^\+\d{10,15}$', cleaned_phone):
            attrs['customer_phone'] = cleaned_phone
        else:
            raise serializers.ValidationError({"customer_phone": "Please enter a valid 10-digit mobile number."})

        return attrs

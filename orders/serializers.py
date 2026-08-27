"""Serializers for orders."""
from rest_framework import serializers
from .models import Order, OrderItem
from payments.models import Payment, Receipt


class OrderItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    emoji = serializers.CharField(source='menu_item.emoji', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'menu_item', 'name', 'item_name_snapshot', 'emoji', 'quantity', 'unit_price', 'subtotal', 'special_instructions']
        read_only_fields = ['unit_price', 'subtotal', 'item_name_snapshot']


class OrderPaymentSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['payment_id', 'payment_method', 'payment_status', 'amount', 'transaction_reference', 'paid_at']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payments = OrderPaymentSummarySerializer(many=True, read_only=True)
    table_number = serializers.CharField(source='table.table_number', read_only=True)
    table_display = serializers.CharField(source='table.display_number', read_only=True)
    customer_name = serializers.CharField(source='customer_name_display', read_only=True)
    customer_phone_masked = serializers.ReadOnlyField()
    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'table_number', 'table_display',
            'customer_name', 'customer_phone_masked',
            'order_status', 'order_status_display',
            'payment_status', 'payment_status_display',
            'payment_method',
            'subtotal', 'discount', 'taxable_amount',
            'cgst_amount', 'sgst_amount', 'tax_amount', 'total_amount',
            'special_instructions', 'items', 'payments',
            'created_at', 'updated_at', 'served_at', 'paid_at', 'completed_at'
        ]
        read_only_fields = fields


class CreateOrderSerializer(serializers.Serializer):
    """Serializer for order creation request."""
    table_number = serializers.CharField(max_length=10)
    customer_session_id = serializers.UUIDField(required=False, allow_null=True)
    idempotency_key = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
    special_instructions = serializers.CharField(required=False, default='', allow_blank=True)
    items = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        error_messages={'min_length': 'Order must contain at least one item.'}
    )

    def validate_items(self, value):
        for item in value:
            if 'menu_item_id' not in item:
                raise serializers.ValidationError("Each item must have a 'menu_item_id'.")
            if 'quantity' not in item or int(item['quantity']) < 1:
                raise serializers.ValidationError("Each item must have a valid 'quantity' (>= 1).")
            item['menu_item_id'] = int(item['menu_item_id'])
            item['quantity'] = int(item['quantity'])
        return value


class OrderStatusUpdateSerializer(serializers.Serializer):
    """Serializer for kitchen status update."""
    status = serializers.ChoiceField(choices=Order.OrderStatus.choices)

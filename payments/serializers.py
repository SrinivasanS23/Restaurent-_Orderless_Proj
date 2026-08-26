"""Serializers for payments."""
from rest_framework import serializers
from .models import Payment, Receipt


class ProcessDeskPaymentSerializer(serializers.Serializer):
    order_number = serializers.CharField(max_length=20)
    payment_method = serializers.ChoiceField(choices=Payment.PaymentMethod.choices)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    cash_amount_received = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    cash_received = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    transaction_reference = serializers.CharField(required=False, default='', allow_blank=True)

    def validate(self, attrs):
        if 'cash_amount_received' not in attrs and 'cash_received' in attrs:
            attrs['cash_amount_received'] = attrs.get('cash_received')
        return attrs


# Alias for backward compatibility
DeskPaymentRequestSerializer = ProcessDeskPaymentSerializer


class PaymentDetailSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    cashier_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'payment_id', 'order_number', 'payment_method', 'payment_status',
            'amount', 'transaction_reference',
            'cash_amount_received', 'cash_change_given', 'cashier_name', 'paid_at'
        ]

    def get_cashier_name(self, obj):
        if obj.cashier:
            return obj.cashier.get_full_name() or obj.cashier.username
        return ''

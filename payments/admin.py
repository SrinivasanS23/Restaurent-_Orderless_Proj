"""Admin configuration for payments, receipts, and audit logs."""
from django.contrib import admin
from .models import Payment, Receipt, PaymentAudit


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'order', 'payment_method', 'payment_status', 'amount', 'transaction_reference', 'cashier', 'paid_at')
    list_filter = ('payment_method', 'payment_status', 'paid_at')
    search_fields = ('order__order_number', 'transaction_reference')
    readonly_fields = ('payment_id', 'paid_at', 'created_at')


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'order', 'delivery_status', 'delivery_channel', 'generated_at')
    list_filter = ('delivery_status', 'delivery_channel', 'generated_at')
    search_fields = ('receipt_number', 'order__order_number')
    readonly_fields = ('generated_at',)


@admin.register(PaymentAudit)
class PaymentAuditAdmin(admin.ModelAdmin):
    list_display = ('order', 'event_type', 'reference', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('order__order_number', 'reference', 'notes')
    readonly_fields = ('created_at',)

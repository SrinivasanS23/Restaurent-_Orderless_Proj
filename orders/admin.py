"""Admin configuration for orders."""
from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('menu_item', 'item_name_snapshot', 'quantity', 'unit_price', 'subtotal', 'special_instructions')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'table', 'customer_name_display',
        'order_status', 'payment_status', 'payment_method',
        'subtotal', 'tax_amount', 'total_amount', 'created_at'
    )
    list_filter = ('order_status', 'payment_status', 'payment_method', 'table', 'created_at')
    search_fields = ('order_number', 'table__table_number', 'customer_session__customer_name', 'customer_session__customer_phone')
    readonly_fields = (
        'order_number', 'subtotal', 'taxable_amount', 'cgst_amount', 'sgst_amount',
        'tax_amount', 'total_amount', 'created_at', 'updated_at', 'served_at', 'paid_at', 'completed_at'
    )
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'item_name_snapshot', 'menu_item', 'quantity', 'unit_price', 'subtotal')
    list_filter = ('order__order_status',)
    search_fields = ('order__order_number', 'item_name_snapshot', 'menu_item__name')

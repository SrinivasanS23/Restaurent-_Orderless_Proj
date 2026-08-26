"""Admin configuration for tables and customer sessions."""
from django.contrib import admin
from .models import RestaurantTable, CustomerSession


@admin.register(RestaurantTable)
class RestaurantTableAdmin(admin.ModelAdmin):
    list_display = ('table_number', 'qr_token', 'active', 'created_at')
    list_filter = ('active',)
    search_fields = ('table_number',)
    readonly_fields = ('qr_token', 'created_at')


@admin.register(CustomerSession)
class CustomerSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'table', 'customer_name', 'masked_phone', 'active', 'created_at', 'last_activity')
    list_filter = ('active', 'table', 'created_at')
    search_fields = ('customer_name', 'customer_phone', 'table__table_number')
    readonly_fields = ('session_id', 'created_at', 'last_activity')

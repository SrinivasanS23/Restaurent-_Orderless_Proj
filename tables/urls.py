"""URL patterns for tables and customer sessions API."""
from django.urls import path
from . import views

urlpatterns = [
    path('tables/<str:table_number>/', views.get_table_by_number, name='api-table-detail'),
    path('tables/<str:table_number>/session-status/', views.check_table_session_status, name='api-table-session-status'),
    path('table-sessions/', views.customer_checkin, name='api-table-session-create'),
    path('customer/session/', views.customer_checkin, name='api-customer-session-alias'),
]

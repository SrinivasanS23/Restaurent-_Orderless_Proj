"""URL patterns for tables and customer sessions API."""
from django.urls import path
from . import views

urlpatterns = [
    # Checkin routes MUST come before tables/<str:table_number>/ to avoid matching 'checkin' as table_number
    path('tables/checkin/', views.customer_checkin, name='api-tables-checkin'),
    path('checkin/', views.customer_checkin, name='api-checkin'),
    path('table-sessions/', views.customer_checkin, name='api-table-session-create'),
    path('customer/session/', views.customer_checkin, name='api-customer-session-alias'),
    
    # Table details and session validation
    path('tables/<str:table_number>/session-status/', views.check_table_session_status, name='api-table-session-status'),
    path('tables/<str:table_number>/', views.get_table_by_number, name='api-table-detail'),
]

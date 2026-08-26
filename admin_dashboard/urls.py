"""URL patterns for admin operations dashboard."""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='admin-dashboard'),
    path('api/stats/', views.dashboard_stats_api, name='admin-dashboard-stats'),
    path('api/orders/', views.orders_list_api, name='admin-dashboard-orders'),
    path('api/orders/<str:order_number>/', views.order_detail_api, name='admin-dashboard-order-detail'),
    path('api/customers/', views.customers_list_api, name='admin-dashboard-customers'),
    path('api/customers/<int:session_id>/', views.customer_detail_api, name='admin-dashboard-customer-detail'),
    # CSV Exports
    path('api/export/orders/csv/', views.export_orders_csv, name='admin-dashboard-export-orders-csv'),
    path('api/export/customers/csv/', views.export_customers_csv, name='admin-dashboard-export-customers-csv'),
    # Add & Edit Menu Items CRUD
    path('api/menu/items/', views.menu_items_api, name='admin-dashboard-menu-items'),
    path('api/menu/items/<int:item_id>/', views.menu_item_detail_api, name='admin-dashboard-menu-item-detail'),
    path('api/menu/categories/', views.menu_categories_api, name='admin-dashboard-menu-categories'),
]

"""URL patterns for customer pages."""
from django.urls import path
from . import views

urlpatterns = [
    path('q/<str:token>/', views.customer_qr_view, name='customer-qr-order'),
    path('<str:table_number>/', views.customer_menu_view, name='customer-menu'),
    path('track/<str:order_number>/', views.customer_order_tracking_view, name='customer-order-tracking'),
]

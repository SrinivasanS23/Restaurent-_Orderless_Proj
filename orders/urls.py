"""URL patterns for orders API."""
from django.urls import path
from . import views

urlpatterns = [
    path('orders/', views.create_order, name='api-create-order'),
    path('orders/create/', views.create_order, name='api-order-create'),
    path('orders/kitchen/', views.get_kitchen_orders, name='api-kitchen-orders'),
    path('orders/<str:order_number>/', views.get_order, name='api-order-detail'),
    path('orders/<int:order_id>/status/', views.update_order_status, name='api-order-status'),
    path('orders/<str:order_number>/receipt/', views.get_order_receipt, name='api-order-receipt'),
    path('orders/<str:order_number>/receipt/pdf/', views.download_order_pdf_receipt, name='api-order-receipt-pdf'),
    path('orders/<str:order_number>/receipt/send/', views.send_receipt_whatsapp, name='api-order-receipt-send'),
]

"""URL patterns for payments API — desk payments only."""
from django.urls import path
from . import views

urlpatterns = [
    path('payments/desk/', views.process_desk_payment, name='api-payment-desk-process'),
    path('payments/desk/order/', views.get_order_for_payment_desk, name='api-payment-desk-order-search-query'),
    path('payments/desk/order/<str:order_number>/', views.get_order_for_payment_desk, name='api-payment-desk-order-search'),
    path('payments/desk/orders/<str:order_number>/', views.get_order_for_payment_desk, name='api-payment-desk-order-search-plural'),
    path('payment/orders/<str:order_number>/', views.get_order_for_payment_desk, name='api-payment-order-detail'),
]

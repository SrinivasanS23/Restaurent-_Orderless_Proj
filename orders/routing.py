"""WebSocket URL routing for orders and kitchen."""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/kitchen/?$', consumers.KitchenConsumer.as_asgi()),
    re_path(r'^ws/orders?/(?P<order_number>[A-Za-z0-9\-]+)/?$', consumers.OrderTrackingConsumer.as_asgi()),
]

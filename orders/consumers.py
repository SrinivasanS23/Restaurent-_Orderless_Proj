"""WebSocket consumers for real-time order updates."""
import json
from channels.generic.websocket import AsyncWebsocketConsumer


class KitchenConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for the kitchen display system."""

    async def connect(self):
        """Join the kitchen group on connection."""
        await self.channel_layer.group_add('kitchen', self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to Kitchen Display System'
        }))

    async def disconnect(self, close_code):
        """Leave the kitchen group on disconnect."""
        try:
            await self.channel_layer.group_discard('kitchen', self.channel_name)
        except Exception:
            pass

    async def kitchen_new_order(self, event):
        """Handle new order event — send to WebSocket."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'new_order',
                'order': event['order']
            }))
        except Exception:
            pass

    async def kitchen_order_update(self, event):
        """Handle order update event — send to WebSocket."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'order_update',
                'order': event['order']
            }))
        except Exception:
            pass


class OrderTrackingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for customer order tracking."""

    async def connect(self):
        """Join the order-specific group on connection."""
        self.order_number = self.scope['url_route']['kwargs']['order_number']
        self.group_name = f'order_{self.order_number}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Tracking order {self.order_number}'
        }))

    async def disconnect(self, close_code):
        """Leave the order group on disconnect."""
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    async def order_status_update(self, event):
        """Handle order status update — send to WebSocket."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'order_update',
                'order': event['order']
            }))
        except Exception:
            pass

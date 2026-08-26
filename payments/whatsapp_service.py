"""WhatsApp receipt delivery service with environment configuration and direct chat link fallback."""
import os
import logging
import urllib.parse
import requests
from django.conf import settings
from .models import Receipt

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service to send order receipts to customer's WhatsApp."""

    @staticmethod
    def get_whatsapp_share_url(order, target_phone=None, receipt_url=None):
        """Build a direct WhatsApp Web/Mobile chat deep link."""
        phone = target_phone or (order.customer_session.customer_phone if order.customer_session else '')
        customer_name = order.customer_name_display
        clean_phone = ''.join(c for c in phone if c.isdigit())
        if clean_phone.startswith('0'):
            clean_phone = clean_phone[1:]
        if len(clean_phone) == 10:
            clean_phone = f"91{clean_phone}"
        
        pdf_link = receipt_url or f"http://127.0.0.1:8000/api/orders/{order.order_number}/receipt/pdf/"
        restaurant = getattr(settings, 'RESTAURANT_NAME', 'OrderLess')
        
        items_summary = "\n".join([f"• {item.name} × {item.quantity} (₹{item.subtotal:.2f})" for item in order.items.all()])

        msg = (
            f"🍽️ *{restaurant} — Official Tax Invoice*\n\n"
            f"Dear {customer_name},\n"
            f"Thank you for dining with us at Table {order.table.table_number}!\n\n"
            f"📋 *Order #*: {order.order_number}\n"
            f"💰 *Total Amount*: ₹{order.total_amount:.2f}\n"
            f"💳 *Status*: {order.get_payment_status_display()}\n\n"
            f"*Items:*\n{items_summary}\n\n"
            f"📄 *Download Official PDF Receipt:*\n{pdf_link}\n\n"
            f"We hope to serve you again soon! ✨"
        )
        return f"https://api.whatsapp.com/send?phone={clean_phone}&text={urllib.parse.quote(msg)}"

    @staticmethod
    def send_receipt(order, target_phone=None, receipt_url=None):
        """
        Attempt to send the receipt to customer's WhatsApp number.
        Returns: tuple of (status: str, message: str, share_url: str)
        """
        phone = target_phone or (order.customer_session.customer_phone if order.customer_session else None)
        customer_name = order.customer_name_display
        share_url = WhatsAppService.get_whatsapp_share_url(order, target_phone=phone, receipt_url=receipt_url)

        if not phone:
            logger.warning(f"No phone number associated with Order {order.order_number}")
            return "NOT_CONFIGURED", "Please provide a mobile number to send the receipt.", share_url

        provider = os.getenv('WHATSAPP_PROVIDER', '').strip()
        account_id = os.getenv('WHATSAPP_ACCOUNT_ID', '').strip()
        auth_token = os.getenv('WHATSAPP_AUTH_TOKEN', '').strip()
        from_number = os.getenv('WHATSAPP_FROM_NUMBER', '').strip()

        receipt, _ = Receipt.objects.get_or_create(
            order=order,
            defaults={'receipt_number': f"REC-{order.order_number}", 'pdf_path': f"receipts/{order.order_number}.pdf"}
        )

        message_body = (
            f"Hi {customer_name}, thank you for dining with us at {getattr(settings, 'RESTAURANT_NAME', 'OrderLess')}! 🍽️\n\n"
            f"Your order #{order.order_number} for Table {order.table.table_number} has been completed.\n"
            f"Total Paid: ₹{order.total_amount:.2f}\n\n"
            f"Official PDF Receipt:\n{receipt_url or 'http://127.0.0.1:8000/api/orders/' + order.order_number + '/receipt/pdf/'}"
        )

        if not (account_id and auth_token and from_number):
            receipt.delivery_status = Receipt.DeliveryStatus.NOT_CONFIGURED
            receipt.delivery_channel = Receipt.DeliveryChannel.WHATSAPP
            receipt.delivery_error_message = "Direct WhatsApp chat link available."
            receipt.save()
            return "NOT_CONFIGURED", "Opening WhatsApp with your official PDF receipt...", share_url

        try:
            if provider.lower() == 'twilio':
                api_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_id}/Messages.json"
                resp = requests.post(
                    api_url,
                    auth=(account_id, auth_token),
                    data={
                        'From': f"whatsapp:{from_number}",
                        'To': f"whatsapp:{phone}",
                        'Body': message_body
                    },
                    timeout=10
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    receipt.delivery_status = Receipt.DeliveryStatus.SUCCESS
                    receipt.delivery_reference = data.get('sid', '')
                    receipt.save()
                    return "SUCCESS", f"Receipt delivered via WhatsApp to {phone}.", share_url
                else:
                    err = f"Provider error ({resp.status_code}): {resp.text}"
                    receipt.delivery_status = Receipt.DeliveryStatus.FAILED
                    receipt.delivery_error_message = err
                    receipt.save()
                    return "FAILED", err, share_url
            else:
                api_url = f"https://graph.facebook.com/v18.0/{from_number}/messages"
                headers = {'Authorization': f"Bearer {auth_token}", 'Content-Type': 'application/json'}
                payload = {
                    "messaging_product": "whatsapp",
                    "to": phone.replace('+', ''),
                    "type": "text",
                    "text": {"body": message_body}
                }
                resp = requests.post(api_url, json=payload, headers=headers, timeout=10)
                if resp.status_code in (200, 201):
                    receipt.delivery_status = Receipt.DeliveryStatus.SUCCESS
                    receipt.save()
                    return "SUCCESS", f"Receipt delivered via WhatsApp to {phone}.", share_url
                else:
                    err = f"Meta API error ({resp.status_code}): {resp.text}"
                    receipt.delivery_status = Receipt.DeliveryStatus.FAILED
                    receipt.delivery_error_message = err
                    receipt.save()
                    return "FAILED", err, share_url
        except Exception as ex:
            err = f"Exception while sending WhatsApp: {str(ex)}"
            receipt.delivery_status = Receipt.DeliveryStatus.FAILED
            receipt.delivery_error_message = err
            receipt.save()
            return "FAILED", err, share_url

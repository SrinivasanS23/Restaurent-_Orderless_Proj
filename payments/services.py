"""Business logic services for desk payments only."""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from orders.services import OrderService
from .models import Payment, PaymentAudit
from .receipt_service import ReceiptService
from .whatsapp_service import WhatsAppService


class PaymentService:

    @staticmethod
    @transaction.atomic
    def process_desk_payment(order_number, payment_method, amount, cashier=None, cash_received=None, reference=''):
        """
        Process payment at physical payment counter.
        Enforces: order must be SERVED, payment must be PENDING.
        Upon payment, marks order COMPLETED & PAID and completes table session.
        """
        try:
            order = Order.objects.select_for_update().get(order_number=order_number.upper())
        except Order.DoesNotExist:
            raise ValueError("Order not found.")

        # Enforce: payment only allowed after SERVED
        if order.order_status != Order.OrderStatus.SERVED:
            if order.order_status == Order.OrderStatus.COMPLETED:
                raise ValueError("This order has already been completed.")
            raise ValueError(
                f"Payment is available after the order has been served. "
                f"Current status: {order.get_order_status_display()}."
            )

        # Prevent duplicate payment
        if order.payment_status == Order.PaymentStatus.PAID:
            raise ValueError("Payment already completed for this order.")

        pay_amount = Decimal(str(amount))
        
        cash_rec = Decimal(str(cash_received)) if cash_received else None
        cash_change = None
        if payment_method == Payment.PaymentMethod.CASH and cash_rec is not None:
            if cash_rec < pay_amount:
                raise ValueError(f"Received cash (₹{cash_rec}) is less than payable amount (₹{pay_amount}).")
            cash_change = cash_rec - pay_amount

        # Guard against AnonymousUser instance
        safe_cashier = cashier if (cashier and cashier.is_authenticated) else None

        payment = Payment.objects.create(
            order=order,
            payment_method=payment_method,
            payment_status=Payment.PaymentStatus.PAID,
            amount=pay_amount,
            transaction_reference=reference,
            cash_amount_received=cash_rec,
            cash_change_given=cash_change,
            cashier=safe_cashier
        )

        # Mark order as paid and completed
        order.payment_status = Order.PaymentStatus.PAID
        order.payment_method = payment_method
        order.order_status = Order.OrderStatus.COMPLETED
        order.paid_at = timezone.now()
        order.completed_at = timezone.now()
        order.save()

        # Deactivate customer session so table is fresh for next customer
        if order.customer_session:
            order.customer_session.close()

        # Generate receipt
        receipt = ReceiptService.generate_pdf_receipt(order)
        wa_status, wa_msg, share_url = WhatsAppService.send_receipt(order)

        PaymentAudit.objects.create(
            order=order,
            event_type='DESK_PAYMENT_COMPLETED',
            reference=reference or str(payment.payment_id),
            notes=f"Order fully paid at desk via {payment_method} (Total: ₹{pay_amount})"
        )

        OrderService._notify_order_update(order)

        try:
            from utils.cloud_db import sync_order_to_cloud
            sync_order_to_cloud(order)
        except Exception:
            pass

        return {
            'payment': payment,
            'order_completed': True,
            'receipt_number': receipt.receipt_number,
            'cash_change': str(cash_change) if cash_change is not None else '0.00',
            'whatsapp_status': wa_status,
            'whatsapp_message': wa_msg,
            'whatsapp_share_url': share_url,
            'message': 'Payment completed. Order marked as completed.'
        }

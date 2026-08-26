"""Models for payments, receipts, and payment audit logs."""
import uuid
from django.db import models
from django.contrib.auth.models import User


class Payment(models.Model):
    """
    Represents a payment transaction for an order.
    Payment is only processed at the physical payment desk.
    """

    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Cash'
        UPI = 'UPI', 'UPI'
        CARD = 'CARD', 'Card'

    class PaymentStatus(models.TextChoices):
        PAID = 'PAID', 'Paid'
        FAILED = 'FAILED', 'Failed'

    payment_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order = models.ForeignKey('orders.Order', on_delete=models.PROTECT, related_name='payments')
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PAID
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_reference = models.CharField(max_length=100, blank=True, default='')
    
    # Cash specific fields
    cash_amount_received = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cash_change_given = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_payments')
    paid_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.payment_id} for {self.order.order_number} - {self.payment_method} ₹{self.amount} ({self.payment_status})"


class Receipt(models.Model):
    """Represents a generated PDF receipt and its dispatch delivery status."""

    class DeliveryStatus(models.TextChoices):
        NOT_ATTEMPTED = 'NOT_ATTEMPTED', 'Not Attempted'
        PENDING = 'PENDING', 'Pending'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'
        NOT_CONFIGURED = 'NOT_CONFIGURED', 'Not Configured'

    class DeliveryChannel(models.TextChoices):
        WHATSAPP = 'WHATSAPP', 'WhatsApp'
        MANUAL_DOWNLOAD = 'MANUAL_DOWNLOAD', 'Manual Download'

    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='receipt')
    receipt_number = models.CharField(max_length=50, unique=True)
    pdf_path = models.CharField(max_length=255, help_text="Relative path to receipt PDF in media storage")
    generated_at = models.DateTimeField(auto_now_add=True)
    
    delivery_status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.NOT_ATTEMPTED
    )
    delivery_channel = models.CharField(
        max_length=20,
        choices=DeliveryChannel.choices,
        default=DeliveryChannel.WHATSAPP
    )
    delivery_reference = models.CharField(max_length=100, blank=True, default='')
    delivery_error_message = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"Receipt {self.receipt_number} for Order {self.order.order_number}"


class PaymentAudit(models.Model):
    """Audit log for tracking payment events, state changes, and idempotency tokens."""
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='audit_logs')
    event_type = models.CharField(max_length=50)
    reference = models.CharField(max_length=100, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Audit {self.event_type} on {self.order.order_number} at {self.created_at}"

"""Order models supporting dine-in table ordering, GST breakdown, and payment at desk."""
import random
import string
from decimal import Decimal
from django.db import models
from django.utils import timezone


class Order(models.Model):
    """Represents a customer dine-in order."""

    class OrderStatus(models.TextChoices):
        ORDER_CREATED = 'ORDER_CREATED', 'Order Created'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        PREPARING = 'PREPARING', 'Preparing'
        READY = 'READY', 'Ready'
        SERVED = 'SERVED', 'Served'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PAID = 'PAID', 'Paid'

    # State machine transition rules
    VALID_TRANSITIONS = {
        'ORDER_CREATED': ['ACCEPTED', 'CANCELLED'],
        'ACCEPTED': ['PREPARING', 'CANCELLED'],
        'PREPARING': ['READY', 'CANCELLED'],
        'READY': ['SERVED', 'CANCELLED'],
        'SERVED': ['COMPLETED'],
        'COMPLETED': [],
        'CANCELLED': [],
    }

    order_number = models.CharField(max_length=20, unique=True, editable=False)
    table = models.ForeignKey('tables.RestaurantTable', on_delete=models.PROTECT, related_name='orders')
    customer_session = models.ForeignKey(
        'tables.CustomerSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )
    order_status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.ORDER_CREATED
    )
    payment_status = models.CharField(
        max_length=25,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    payment_method = models.CharField(
        max_length=10,
        blank=True,
        default='',
        help_text="Summary payment method set after payment (CASH/UPI/CARD)"
    )

    # Billing & GST Breakdown
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    special_instructions = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    served_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        if self.order_status == self.OrderStatus.SERVED and not self.served_at:
            self.served_at = timezone.now()
        if self.order_status == self.OrderStatus.COMPLETED and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_order_number():
        """Generate unique order number like ORD-A5X2."""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            order_number = f"ORD-{code}"
            if not Order.objects.filter(order_number=order_number).exists():
                return order_number

    def can_transition_to(self, new_status):
        """Check if the order can transition to the given status."""
        valid_next = self.VALID_TRANSITIONS.get(self.order_status, [])
        return new_status in valid_next

    def calculate_totals(self, gst_percentage=Decimal('5.0')):
        """Recalculate subtotal, GST (CGST 2.5% + SGST 2.5%), and total amount."""
        items_subtotal = sum(item.subtotal for item in self.items.all())
        self.subtotal = items_subtotal
        self.taxable_amount = max(Decimal('0.00'), self.subtotal - self.discount)
        half_rate = gst_percentage / Decimal('2.0')
        self.cgst_amount = (self.taxable_amount * (half_rate / Decimal('100.0'))).quantize(Decimal('0.01'))
        self.sgst_amount = (self.taxable_amount * (half_rate / Decimal('100.0'))).quantize(Decimal('0.01'))
        self.tax_amount = self.cgst_amount + self.sgst_amount
        self.total_amount = (self.taxable_amount + self.tax_amount).quantize(Decimal('0.01'))

    @property
    def customer_name_display(self):
        if self.customer_session and self.customer_session.customer_name:
            return self.customer_session.customer_name
        return "Guest"

    @property
    def customer_phone_masked(self):
        if self.customer_session and self.customer_session.customer_phone:
            return self.customer_session.masked_phone
        return ""

    def __str__(self):
        return f"{self.order_number} - Table {self.table.table_number} ({self.order_status})"


class OrderItem(models.Model):
    """Individual line item in an order."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey('menu.MenuItem', on_delete=models.PROTECT, related_name='order_items')
    item_name_snapshot = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Menu item name at time of purchase (historical preservation)"
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    special_instructions = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):
        if not self.unit_price and self.menu_item:
            self.unit_price = self.menu_item.price
        if not self.item_name_snapshot and self.menu_item:
            self.item_name_snapshot = self.menu_item.name
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    @property
    def name(self):
        """Return snapshot name if available, otherwise live menu item name."""
        if self.item_name_snapshot:
            return self.item_name_snapshot
        return self.menu_item.name if self.menu_item else ""

    def __str__(self):
        return f"{self.quantity}x {self.name} ({self.order.order_number})"

"""Models for restaurant tables and customer dining sessions."""
import uuid
from django.db import models
from django.utils import timezone


class RestaurantTable(models.Model):
    """Represents a physical table in the restaurant."""
    table_number = models.CharField(max_length=10, unique=True, help_text="e.g. T01, T02")
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['table_number']

    def __str__(self):
        return f"Table {self.table_number}"

    @property
    def display_number(self):
        """Return just the numeric part for display, e.g. '05' from 'T05'."""
        return self.table_number.replace('T', '')


class CustomerSession(models.Model):
    """
    Represents a specific dining visit session at a physical table.
    A table has many historical sessions over time.
    When an order is paid and completed, the session is CLOSED.
    """

    class SessionStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        CLOSED = 'CLOSED', 'Closed'

    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    table = models.ForeignKey(RestaurantTable, on_delete=models.CASCADE, related_name='customer_sessions')
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=20, help_text="Normalized customer phone number")
    status = models.CharField(max_length=10, choices=SessionStatus.choices, default=SessionStatus.ACTIVE)
    active = models.BooleanField(default=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Session {self.session_id} - {self.customer_name} ({self.table.table_number}) [{self.status}]"

    def close(self):
        """Close the table session after payment settlement."""
        self.status = self.SessionStatus.CLOSED
        self.active = False
        if not self.ended_at:
            self.ended_at = timezone.now()
        self.save(update_fields=['status', 'active', 'ended_at', 'last_activity'])

    @property
    def masked_phone(self):
        """Mask phone for privacy, e.g. +91 ******3210."""
        if len(self.customer_phone) > 4:
            return self.customer_phone[:3] + "******" + self.customer_phone[-4:]
        return self.customer_phone

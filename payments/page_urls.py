"""URL patterns for payment desk page."""
from django.urls import path
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def payment_desk_view(request):
    """Render the payment desk interface."""
    return render(request, 'payment/desk.html')


urlpatterns = [
    path('', payment_desk_view, name='payment-desk'),
]

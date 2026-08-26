"""Views for kitchen display system."""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings


@login_required
def kitchen_dashboard_view(request):
    """Render the kitchen display system dashboard."""
    return render(request, 'kitchen/dashboard.html', {
        'restaurant_name': settings.RESTAURANT_NAME,
    })

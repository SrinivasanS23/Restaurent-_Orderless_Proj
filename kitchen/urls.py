"""URL patterns for kitchen pages."""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.kitchen_dashboard_view, name='kitchen-dashboard'),
]

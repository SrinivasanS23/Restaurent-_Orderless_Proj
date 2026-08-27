"""URL patterns for menu API."""
from django.urls import path
from . import views

urlpatterns = [
    path('menu/', views.get_menu, name='api-menu'),
    path('menu/categories/', views.get_categories, name='api-menu-categories'),
    path('menu/items/<int:item_id>/toggle/', views.toggle_menu_item, name='api-menu-item-toggle'),
]

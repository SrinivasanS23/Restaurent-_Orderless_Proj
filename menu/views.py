"""API views for menu."""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import MenuCategory, MenuItem
from .serializers import MenuCategorySerializer, MenuItemSerializer


@api_view(['GET'])
def get_menu(request):
    """Get full menu with categories and items."""
    categories = MenuCategory.objects.filter(active=True).prefetch_related(
        'items'
    )
    # Filter to only available items on the frontend
    serializer = MenuCategorySerializer(categories, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def get_categories(request):
    """Get menu categories list."""
    categories = MenuCategory.objects.filter(active=True)
    data = [{'id': c.id, 'name': c.name, 'icon': c.icon} for c in categories]
    return Response(data)

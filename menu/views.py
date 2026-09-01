"""API views for menu."""
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework import status
from .models import MenuCategory, MenuItem
from .serializers import MenuCategorySerializer, MenuItemSerializer


from django.db.models import Prefetch

@api_view(['GET'])
@permission_classes([AllowAny])
def get_menu(request):
    """Get full menu with categories and items."""
    try:
        from utils.cloud_db import pull_and_sync_menu_from_cloud
        pull_and_sync_menu_from_cloud()
    except Exception:
        pass
    categories = MenuCategory.objects.filter(active=True).prefetch_related(
        Prefetch('items', queryset=MenuItem.objects.filter(is_deleted=False))
    )
    serializer = MenuCategorySerializer(categories, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_categories(request):
    """Get menu categories list."""
    categories = MenuCategory.objects.filter(active=True)
    data = [{'id': c.id, 'name': c.name, 'icon': c.icon} for c in categories]
    return Response(data)


@api_view(['POST', 'PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def toggle_menu_item(request, item_id):
    """Toggle item availability in real-time (Staff & Admin)."""
    if not request.user.is_staff:
        return Response({'error': 'Staff permission required'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        item = MenuItem.objects.get(id=item_id)
    except MenuItem.DoesNotExist:
        return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if 'available' in request.data:
        item.available = bool(request.data['available'])
    else:
        item.available = not item.available
    item.save()

    return Response({
        'success': True,
        'item_id': item.id,
        'name': item.name,
        'available': item.available,
        'message': f"'{item.name}' is now {'In Stock' if item.available else 'Out of Stock'}"
    })

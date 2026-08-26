"""URL configuration for OrderLess project."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from security.views import SecureLoginView, SecureLogoutView, health_check_view
from customer.views import customer_home_view

urlpatterns = [
    path('', customer_home_view, name='home'),
    path('health/', health_check_view, name='health-check'),
    path('admin/', admin.site.urls),
    path('login/', SecureLoginView.as_view(), name='login'),
    path('logout/', SecureLogoutView.as_view(), name='logout'),
    path('api/', include('tables.urls')),
    path('api/', include('menu.urls')),
    path('api/', include('orders.urls')),
    path('api/', include('payments.urls')),
    path('order/', include('customer.urls')),
    path('kitchen/', include('kitchen.urls')),
    path('payment/', include('payments.page_urls')),
    path('dashboard/', include('admin_dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

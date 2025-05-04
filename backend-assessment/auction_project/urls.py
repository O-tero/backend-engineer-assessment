from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Define API URL patterns that will be included in Swagger docs
api_urlpatterns = [
    path('api/v1/', include('core.urls')),
]

# Swagger documentation setup
schema_view = get_schema_view(
    openapi.Info(
        title="Auction API",
        default_version='v1',
        description="API for an auction system",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@auction.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    patterns=api_urlpatterns, 
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API routes - ensure v1 version is in the path
    path('api/v1/', include('core.urls')),
    
    # API Documentation - with proper paths
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/docs/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

urlpatterns += api_urlpatterns
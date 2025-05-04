from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import UserSerializer


class RegisterView(APIView):
    """
    API endpoint for user registration.
    """
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password'],
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Username'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='Password'),
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='Email address'),
                'first_name': openapi.Schema(type=openapi.TYPE_STRING, description='First name'),
                'last_name': openapi.Schema(type=openapi.TYPE_STRING, description='Last name'),
            },
        ),
        responses={
            201: UserSerializer,
            400: 'Bad Request - Invalid data'
        },
        operation_description="Create a new user account"
    )
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """
    API endpoint for retrieving the current user's profile.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: UserSerializer,
            401: 'Unauthorized - Authentication credentials not provided'
        },
        operation_description="Get the currently logged-in user's profile"
    )
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
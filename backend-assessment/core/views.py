from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth.models import User

from .models import Auction, Bid
from .serializers import (
    UserSerializer,
    AuctionListSerializer,
    AuctionDetailSerializer,
    AuctionCreateSerializer,
    BidSerializer
)
from .permissions import IsOwnerOrAdmin, IsAdminUser, CanBidOnAuction


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for user registration and management.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_permissions(self):
        """
        Only allow anyone to register (create) a user.
        All other operations require authentication.
        """
        if self.action == 'create':
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Non-admin users can only see their own profile.
        """
        user = self.request.user
        if user.is_staff:
            return User.objects.all()
        elif user.is_authenticated:
            return User.objects.filter(id=user.id)
        return User.objects.none()


class AuctionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for auctions.
    """
    queryset = Auction.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'end_time', 'current_price']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AuctionCreateSerializer
        elif self.action in ['retrieve', 'bids']:
            return AuctionDetailSerializer
        return AuctionListSerializer
    
    def get_permissions(self):
        """
        Define permissions based on the action:
        - List and retrieve: Any authenticated user
        - Create: Any authenticated user
        - Update and delete: Only owner or admin
        - Bids: Anyone who can bid (not the creator)
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
        elif self.action == 'bids':
            permission_classes = [permissions.IsAuthenticated, CanBidOnAuction]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter auctions based on query parameters:
        - status: Filter by auction status (pending, active, closed)
        - creator: Filter by auction creator
        - my: Filter to only show user's auctions (if true)
        - won: Filter to only show auctions won by user (if true)
        """
        queryset = Auction.objects.all()
        
        # Apply filters based on query parameters
        status = self.request.query_params.get('status')
        creator_id = self.request.query_params.get('creator')
        my_auctions = self.request.query_params.get('my')
        won_auctions = self.request.query_params.get('won')
        
        if status:
            queryset = queryset.filter(status=status)
        
        if creator_id:
            queryset = queryset.filter(creator_id=creator_id)
        
        if my_auctions and my_auctions.lower() == 'true' and self.request.user.is_authenticated:
            queryset = queryset.filter(creator=self.request.user)
        
        if won_auctions and won_auctions.lower() == 'true' and self.request.user.is_authenticated:
            queryset = queryset.filter(winner=self.request.user)
        
        return queryset
    
    def perform_create(self, serializer):
        """
        Set the creator to the current authenticated user.
        """
        serializer.save(creator=self.request.user)
    
    @action(detail=True, methods=['get'])
    def bids(self, request, pk=None):
        """
        Get all bids for a specific auction.
        """
        auction = self.get_object()
        bids = auction.bids.all()
        serializer = BidSerializer(bids, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def place_bid(self, request, pk=None):
        """
        Place a bid on a specific auction.
        """
        auction = self.get_object()
        
        # Check if auction is active
        if not auction.is_active:
            return Response(
                {"detail": "This auction is not active"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user is trying to bid on their own auction
        if auction.creator == request.user:
            return Response(
                {"detail": "You cannot bid on your own auction"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create serializer with the auction already set
        data = request.data.copy()
        data['auction'] = auction.id
        
        serializer = BidSerializer(
            data=data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            # Return the updated auction
            auction_serializer = AuctionDetailSerializer(auction)
            return Response(auction_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BidViewSet(viewsets.ModelViewSet):
    """
    API endpoint for bids.
    Users can only view their own bids unless they're an admin.
    """
    queryset = Bid.objects.all()
    serializer_class = BidSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        """
        Define permissions based on the action:
        - List and retrieve: Any authenticated user (filtered to own bids)
        - Create: Any authenticated user (validated in serializer for auction rules)
        - Update and delete: Not allowed (bids cannot be modified)
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter bids based on query parameters and user:
        - auction: Filter by auction ID
        - Non-admin users can only see their own bids
        """
        user = self.request.user
        queryset = Bid.objects.all()
        
        # Filter by auction if provided
        auction_id = self.request.query_params.get('auction')
        if auction_id:
            queryset = queryset.filter(auction_id=auction_id)
        
        # Non-admin users can only see their own bids
        if not user.is_staff:
            queryset = queryset.filter(bidder=user)
            
        return queryset
    
    def perform_create(self, serializer):
        """
        Set the bidder to the current authenticated user.
        """
        serializer.save(bidder=self.request.user)
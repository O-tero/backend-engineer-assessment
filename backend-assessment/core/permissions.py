from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admins to view or edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Admin permissions
        if request.user.is_staff:
            return True
        
        # Check if the object has a creator attribute (like Auction)
        if hasattr(obj, 'creator'):
            return obj.creator == request.user
            
        # Check if the object has a bidder attribute (like Bid)
        if hasattr(obj, 'bidder'):
            return obj.bidder == request.user
            
        return False


class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admin users to access the view.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class CanBidOnAuction(permissions.BasePermission):
    """
    Custom permission to check if a user can bid on an auction.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
        
    def has_object_permission(self, request, view, obj):
        # Ensure the auction is active
        if not obj.is_active:
            return False
            
        # Ensure the user is not the auction creator
        if obj.creator == request.user:
            return False
            
        return True
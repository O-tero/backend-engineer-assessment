from django.contrib import admin
from .models import Auction, Bid


class BidInline(admin.TabularInline):
    model = Bid
    fields = ('bidder', 'amount', 'created_at')
    readonly_fields = ('bidder', 'amount', 'created_at')
    extra = 0
    can_delete = False
    ordering = ('-amount',)
    

@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'starting_price', 'current_price', 'status', 'start_time', 'end_time', 'winner')
    list_filter = ('status', 'created_at', 'start_time', 'end_time')
    search_fields = ('title', 'description', 'creator__username')
    readonly_fields = ('current_price', 'winner', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [BidInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'creator')
        }),
        ('Pricing', {
            'fields': ('starting_price', 'current_price')
        }),
        ('Auction Timing', {
            'fields': ('start_time', 'end_time', 'status')
        }),
        ('Results', {
            'fields': ('winner',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_change_permission(self, request, obj=None):
        # Prevent editing closed auctions
        if obj and obj.status == 'closed':
            return False
        return super().has_change_permission(request, obj)


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('id', 'auction', 'bidder', 'amount', 'created_at')
    list_filter = ('created_at', 'auction')
    search_fields = ('auction__title', 'bidder__username')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    
    def has_change_permission(self, request, obj=None):
        # Bids cannot be edited after creation
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Only admins can delete bids and only for open auctions
        if obj and obj.auction.status != 'active':
            return False
        return super().has_delete_permission(request, obj)
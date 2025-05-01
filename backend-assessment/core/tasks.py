from celery import shared_task
from django.utils import timezone
from django.db.models import Max, F, Q

@shared_task
def check_expired_auctions():
    """
    Check for auctions that have ended but not been marked as closed.
    For each closed auction, determine the winner and update the auction.
    """
    from .models import Auction, Bid
    
    # Get active auctions that have ended
    now = timezone.now()
    expired_auctions = Auction.objects.filter(
        status='active',
        end_time__lte=now
    )
    
    closed_count = 0
    for auction in expired_auctions:
        # Get the highest bid
        highest_bid = auction.bids.order_by('-amount').first()
        
        # Update auction status
        auction.status = 'closed'
        
        # Set winner if there were bids
        if highest_bid:
            auction.winner = highest_bid.bidder
            
        auction.save(update_fields=['status', 'winner', 'updated_at'])
        closed_count += 1
    
    return f"Closed {closed_count} auctions"


@shared_task
def update_auction_statuses():
    """
    Update auction statuses based on start_time and end_time.
    """
    from .models import Auction
    
    now = timezone.now()
    
    # Update pending auctions that should be active
    pending_to_active = Auction.objects.filter(
        status='pending',
        start_time__lte=now,
        end_time__gt=now
    ).update(status='active')
    
    # Update active auctions that should be closed
    active_to_closed = Auction.objects.filter(
        status='active',
        end_time__lte=now
    )
    
    closed_count = 0
    for auction in active_to_closed:
        # Get the highest bid
        highest_bid = auction.bids.order_by('-amount').first()
        
        # Update auction status and winner
        auction.status = 'closed'
        if highest_bid:
            auction.winner = highest_bid.bidder
            
        auction.save(update_fields=['status', 'winner', 'updated_at'])
        closed_count += 1
    
    return f"Updated {pending_to_active} pending auctions to active and {closed_count} active auctions to closed"
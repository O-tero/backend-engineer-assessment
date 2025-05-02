from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Auction, Bid


@receiver(post_save, sender=Bid)
def update_auction_on_bid(sender, instance, created, **kwargs):
    """
    When a new bid is created, update the auction's current price.
    """
    if created and instance.amount > instance.auction.current_price:
        auction = instance.auction
        auction.current_price = instance.amount
        auction.save(update_fields=['current_price', 'updated_at'])


@receiver(pre_save, sender=Auction)
def update_auction_status(sender, instance, **kwargs):
    """
    Update auction status based on current time before saving.
    """
    now = timezone.now()
    
    # Skip if this is a new auction (status will be set in the model's save method)
    if not instance.pk:
        return
        
    # Get previous state to check if we need to update
    try:
        old_instance = Auction.objects.get(pk=instance.pk)
        old_status = old_instance.status
    except Auction.DoesNotExist:
        # This shouldn't happen in pre_save but handle it just in case
        old_status = None
    
    # Update status based on time if it hasn't been manually changed
    if instance.status == old_status:
        if instance.start_time <= now < instance.end_time:
            instance.status = 'active'
        elif now >= instance.end_time:
            instance.status = 'closed'
            
            # Set winner if auction is closing and has bids
            if old_status != 'closed' and not instance.winner:
                highest_bid = instance.bids.order_by('-amount').first()
                if highest_bid:
                    instance.winner = highest_bid.bidder
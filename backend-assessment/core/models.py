from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError


class Auction(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    starting_price = models.DecimalField(max_digits=10, decimal_places=2)
    current_price = models.DecimalField(max_digits=10, decimal_places=2)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auctions_created')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    winner = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='auctions_won'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['end_time']),
        ]

    def __str__(self):
        return f"{self.title} (Status: {self.status})"

    def clean(self):
        # Validate that end_time is after start_time
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time")
        
        # Validate that start_time is not in the past when creating
        if not self.pk and self.start_time < timezone.now():
            raise ValidationError("Start time cannot be in the past")

    def save(self, *args, **kwargs):
        # Set current_price to starting_price if this is a new auction
        if not self.pk:
            self.current_price = self.starting_price
            
        # Update status based on time
        now = timezone.now()
        if self.start_time <= now < self.end_time:
            self.status = 'active'
        elif now >= self.end_time:
            self.status = 'closed'

        self.clean()
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        now = timezone.now()
        return self.status == 'active' and self.start_time <= now < self.end_time

    @property
    def highest_bid(self):
        return self.bids.order_by('-amount').first()


class Bid(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bids')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-amount']
        indexes = [
            models.Index(fields=['auction', 'amount']),
            models.Index(fields=['bidder']),
        ]

    def __str__(self):
        return f"Bid of ${self.amount} by {self.bidder.username} on {self.auction.title}"

    def clean(self):
        # Check if the auction is active
        if not self.auction.is_active:
            raise ValidationError("Cannot place bid on an inactive auction")
        
        # Ensure bid amount is greater than current auction price
        if self.amount <= self.auction.current_price:
            raise ValidationError(f"Bid amount must be greater than current price (${self.auction.current_price})")
        
        # Prevent bidding on own auction
        if self.bidder == self.auction.creator:
            raise ValidationError("Cannot bid on your own auction")

    def save(self, *args, **kwargs):
        self.clean()
        
        # Update auction's current price
        if self.amount > self.auction.current_price:
            self.auction.current_price = self.amount
            self.auction.save(update_fields=['current_price', 'updated_at'])
            
        super().save(*args, **kwargs)
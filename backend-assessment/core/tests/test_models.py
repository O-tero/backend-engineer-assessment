from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from core.models import Auction, Bid


class AuctionModelTest(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create a basic auction
        self.now = timezone.now()
        self.auction = Auction.objects.create(
            title='Test Auction',
            description='This is a test auction',
            starting_price=100.00,
            current_price=100.00,
            creator=self.user,
            start_time=self.now,
            end_time=self.now + timedelta(days=7),
            status='active'
        )
    
    def test_auction_creation(self):
        """Test that an auction can be created properly"""
        self.assertEqual(self.auction.title, 'Test Auction')
        self.assertEqual(self.auction.starting_price, 100.00)
        self.assertEqual(self.auction.status, 'active')
        self.assertEqual(self.auction.creator, self.user)
    
    def test_auction_string_representation(self):
        """Test the string representation of an auction"""
        self.assertEqual(str(self.auction), 'Test Auction (Status: active)')
    
    def test_auction_validation_end_time(self):
        """Test that an auction's end time must be after its start time"""
        # Create an auction with end_time before start_time
        auction = Auction(
            title='Invalid Auction',
            description='This auction has invalid times',
            starting_price=50.00,
            current_price=50.00,
            creator=self.user,
            start_time=self.now,
            end_time=self.now - timedelta(hours=1)
        )
        
        # Validation should fail
        with self.assertRaises(ValidationError):
            auction.full_clean()
    
    def test_auction_validation_start_time_past(self):
        """Test that a new auction's start time cannot be in the past"""
        # Create an auction with start_time in the past
        auction = Auction(
            title='Past Auction',
            description='This auction starts in the past',
            starting_price=50.00,
            current_price=50.00,
            creator=self.user,
            start_time=self.now - timedelta(days=1),
            end_time=self.now + timedelta(days=6)
        )
        
        # Validation should fail
        with self.assertRaises(ValidationError):
            auction.full_clean()
    
    def test_auction_is_active_property(self):
        """Test the is_active property of an auction"""
        # Active auction
        self.assertTrue(self.auction.is_active)
        
        # Pending auction
        future_auction = Auction.objects.create(
            title='Future Auction',
            description='This auction starts in the future',
            starting_price=150.00,
            current_price=150.00,
            creator=self.user,
            start_time=self.now + timedelta(days=1),
            end_time=self.now + timedelta(days=8),
            status='pending'
        )
        self.assertFalse(future_auction.is_active)
        
        # Closed auction
        closed_auction = Auction.objects.create(
            title='Closed Auction',
            description='This auction is closed',
            starting_price=200.00,
            current_price=200.00,
            creator=self.user,
            start_time=self.now - timedelta(days=14),
            end_time=self.now - timedelta(days=7),
            status='closed'
        )
        self.assertFalse(closed_auction.is_active)


class BidModelTest(TestCase):
    def setUp(self):
        # Create test users
        self.seller = User.objects.create_user(
            username='seller',
            password='sellerpass123'
        )
        
        self.bidder = User.objects.create_user(
            username='bidder',
            password='bidderpass123'
        )
        
        # Create a test auction
        self.now = timezone.now()
        self.auction = Auction.objects.create(
            title='Test Auction',
            description='This is a test auction',
            starting_price=100.00,
            current_price=100.00,
            creator=self.seller,
            start_time=self.now,
            end_time=self.now + timedelta(days=7),
            status='active'
        )
        
        # Create a test bid
        self.bid = Bid.objects.create(
            auction=self.auction,
            bidder=self.bidder,
            amount=150.00
        )
    
    def test_bid_creation(self):
        """Test that a bid can be created properly"""
        self.assertEqual(self.bid.auction, self.auction)
        self.assertEqual(self.bid.bidder, self.bidder)
        self.assertEqual(self.bid.amount, 150.00)
        
        # Check that the auction's current price was updated
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, 150.00)
    
    def test_bid_string_representation(self):
        """Test the string representation of a bid"""
        expected_str = f"Bid of $150.00 by bidder on Test Auction"
        self.assertEqual(str(self.bid), expected_str)
    
    def test_bid_validation_inactive_auction(self):
        """Test that bids cannot be placed on inactive auctions"""
        # Create a closed auction
        closed_auction = Auction.objects.create(
            title='Closed Auction',
            description='This auction is closed',
            starting_price=200.00,
            current_price=200.00,
            creator=self.seller,
            start_time=self.now - timedelta(days=14),
            end_time=self.now - timedelta(days=7),
            status='closed'
        )
        
        # Attempt to create a bid on the closed auction
        bid = Bid(
            auction=closed_auction,
            bidder=self.bidder,
            amount=250.00
        )
        
        # Validation should fail
        with self.assertRaises(ValidationError):
            bid.full_clean()
    
    def test_bid_validation_low_amount(self):
        """Test that bids must be higher than the current price"""
        # Attempt to create a bid with an amount equal to current price
        bid = Bid(
            auction=self.auction,
            bidder=self.bidder,
            amount=self.auction.current_price
        )
        
        # Validation should fail
        with self.assertRaises(ValidationError):
            bid.full_clean()
    
    def test_bid_validation_own_auction(self):
        """Test that users cannot bid on their own auctions"""
        # Attempt to create a bid by the auction creator
        bid = Bid(
            auction=self.auction,
            bidder=self.seller,  # This is the auction creator
            amount=200.00
        )
        
        # Validation should fail
        with self.assertRaises(ValidationError):
            bid.full_clean()
    
    def test_multiple_bids_highest_wins(self):
        """Test that with multiple bids, the highest one is reflected in the auction"""
        # Create another bidder
        bidder2 = User.objects.create_user(
            username='bidder2',
            password='bidder2pass123'
        )
        
        # Place a higher bid
        bid2 = Bid.objects.create(
            auction=self.auction,
            bidder=bidder2,
            amount=200.00
        )
        
        # Check that the auction's current price was updated
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, 200.00)
        
        # Check highest_bid property
        self.assertEqual(self.auction.highest_bid, bid2)
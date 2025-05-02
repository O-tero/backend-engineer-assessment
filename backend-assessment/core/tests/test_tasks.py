from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
from unittest.mock import patch
import factory

from .models import Auction, Bid
from .tasks import check_expired_auctions, update_auction_statuses


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'password')


class AuctionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Auction

    title = factory.Sequence(lambda n: f'Test Auction {n}')
    description = factory.Faker('paragraph')
    starting_price = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    creator = factory.SubFactory(UserFactory)
    status = 'pending'
    
    @factory.lazy_attribute
    def start_time(self):
        return timezone.now() + timedelta(hours=1)
    
    @factory.lazy_attribute
    def end_time(self):
        return self.start_time + timedelta(days=3)
    
    @factory.lazy_attribute
    def current_price(self):
        return self.starting_price


class BidFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Bid

    auction = factory.SubFactory(AuctionFactory)
    bidder = factory.SubFactory(UserFactory)
    
    @factory.lazy_attribute
    def amount(self):
        return self.auction.current_price + 10.00


class CheckExpiredAuctionsTestCase(TestCase):
    def setUp(self):
        # Create users
        self.seller = UserFactory()
        self.bidder1 = UserFactory()
        self.bidder2 = UserFactory()
        
        # Time references
        self.now = timezone.now()
        self.past = self.now - timedelta(hours=1)
        self.future = self.now + timedelta(hours=1)
        
        # Create auction scenarios
        with patch('django.utils.timezone.now', return_value=self.now):
            # Active auction that has ended (should be closed)
            self.expired_auction = AuctionFactory(
                creator=self.seller,
                start_time=self.past - timedelta(days=5),
                end_time=self.past,
                status='active'
            )
            
            # Active auction that hasn't ended yet (should remain active)
            self.active_auction = AuctionFactory(
                creator=self.seller,
                start_time=self.past,
                end_time=self.future,
                status='active'
            )
            
            # Already closed auction (should remain closed)
            self.closed_auction = AuctionFactory(
                creator=self.seller,
                start_time=self.past - timedelta(days=5),
                end_time=self.past - timedelta(days=2),
                status='closed'
            )
    
    def test_check_expired_auctions_normal_case(self):
        """Test that expired auctions with bids are closed and winners are set correctly"""
        # Add bids to the expired auction
        bid1 = BidFactory(
            auction=self.expired_auction,
            bidder=self.bidder1,
            amount=self.expired_auction.current_price + 10
        )
        bid2 = BidFactory(
            auction=self.expired_auction,
            bidder=self.bidder2,
            amount=self.expired_auction.current_price + 20
        )
        
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            result = check_expired_auctions()
        
        # Get fresh data from database
        self.expired_auction.refresh_from_db()
        
        # Assert the auction is closed
        self.assertEqual(self.expired_auction.status, 'closed')
        # Assert the winner is set to the highest bidder
        self.assertEqual(self.expired_auction.winner, self.bidder2)
        # Assert the result message is correct
        self.assertEqual(result, "Closed 1 auctions")
    
    def test_check_expired_auctions_no_bids(self):
        """Test that expired auctions with no bids are closed but have no winner"""
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            result = check_expired_auctions()
        
        # Get fresh data from database
        self.expired_auction.refresh_from_db()
        
        # Assert the auction is closed
        self.assertEqual(self.expired_auction.status, 'closed')
        # Assert there is no winner
        self.assertIsNone(self.expired_auction.winner)
        # Assert the result message is correct
        self.assertEqual(result, "Closed 1 auctions")
    
    def test_check_expired_auctions_non_expired_unchanged(self):
        """Test that non-expired auctions are not affected"""
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            check_expired_auctions()
        
        # Get fresh data from database
        self.active_auction.refresh_from_db()
        
        # Assert the auction is still active
        self.assertEqual(self.active_auction.status, 'active')
        # Assert there is no winner
        self.assertIsNone(self.active_auction.winner)
    
    def test_check_expired_auctions_already_closed_unchanged(self):
        """Test that already closed auctions are not affected"""
        # Set a winner for the closed auction
        self.closed_auction.winner = self.bidder1
        self.closed_auction.save()
        
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            check_expired_auctions()
        
        # Get fresh data from database
        self.closed_auction.refresh_from_db()
        
        # Assert the auction is still closed
        self.assertEqual(self.closed_auction.status, 'closed')
        # Assert the winner is unchanged
        self.assertEqual(self.closed_auction.winner, self.bidder1)
    
    def test_check_expired_auctions_multiple_auctions(self):
        """Test handling multiple expired auctions at once"""
        # Create another expired auction
        with patch('django.utils.timezone.now', return_value=self.now):
            second_expired_auction = AuctionFactory(
                creator=self.seller,
                start_time=self.past - timedelta(days=3),
                end_time=self.past - timedelta(hours=2),
                status='active'
            )
        
        # Add bids to both auctions
        BidFactory(auction=self.expired_auction, bidder=self.bidder1)
        BidFactory(auction=second_expired_auction, bidder=self.bidder2)
        
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            result = check_expired_auctions()
        
        # Get fresh data from database
        self.expired_auction.refresh_from_db()
        second_expired_auction.refresh_from_db()
        
        # Assert both auctions are closed
        self.assertEqual(self.expired_auction.status, 'closed')
        self.assertEqual(second_expired_auction.status, 'closed')
        # Assert the winners are set correctly
        self.assertEqual(self.expired_auction.winner, self.bidder1)
        self.assertEqual(second_expired_auction.winner, self.bidder2)
        # Assert the result message is correct
        self.assertEqual(result, "Closed 2 auctions")
    
    def test_check_expired_auctions_edge_case_no_expired(self):
        """Test behavior when no auctions are expired"""
        # Close or make all auctions non-expired
        self.expired_auction.status = 'closed'
        self.expired_auction.save()
        
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            result = check_expired_auctions()
        
        # Assert the result message indicates no auctions were closed
        self.assertEqual(result, "Closed 0 auctions")


class UpdateAuctionStatusesTestCase(TestCase):
    def setUp(self):
        # Create users
        self.seller = UserFactory()
        self.bidder1 = UserFactory()
        self.bidder2 = UserFactory()
        
        # Time references
        self.now = timezone.now()
        self.past = self.now - timedelta(hours=1)
        self.future = self.now + timedelta(hours=1)
        
        # Create auction scenarios
        with patch('django.utils.timezone.now', return_value=self.now):
            # Pending auction with start time in the past (should become active)
            self.pending_to_active = AuctionFactory(
                creator=self.seller,
                start_time=self.past,
                end_time=self.future,
                status='pending'
            )
            
            # Pending auction with start time in the future (should stay pending)
            self.staying_pending = AuctionFactory(
                creator=self.seller,
                start_time=self.future,
                end_time=self.future + timedelta(days=1),
                status='pending'
            )
            
            # Active auction with end time in the past (should become closed)
            self.active_to_closed = AuctionFactory(
                creator=self.seller,
                start_time=self.past - timedelta(days=2),
                end_time=self.past,
                status='active'
            )
            
            # Active auction with end time in the future (should stay active)
            self.staying_active = AuctionFactory(
                creator=self.seller,
                start_time=self.past,
                end_time=self.future,
                status='active'
            )
            
            # Already closed auction (should stay closed)
            self.closed_auction = AuctionFactory(
                creator=self.seller,
                start_time=self.past - timedelta(days=5),
                end_time=self.past - timedelta(days=2),
                status='closed'
            )
    
    def test_update_auction_statuses_normal_case(self):
        """Test normal transition of auction statuses"""
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            result = update_auction_statuses()
        
        # Get fresh data from database
        self.pending_to_active.refresh_from_db()
        self.staying_pending.refresh_from_db()
        self.active_to_closed.refresh_from_db()
        self.staying_active.refresh_from_db()
        self.closed_auction.refresh_from_db()
        
        # Assert the statuses are updated correctly
        self.assertEqual(self.pending_to_active.status, 'active')
        self.assertEqual(self.staying_pending.status, 'pending')
        self.assertEqual(self.active_to_closed.status, 'closed')
        self.assertEqual(self.staying_active.status, 'active')
        self.assertEqual(self.closed_auction.status, 'closed')
        
        # Assert the result message is correct
        self.assertEqual(result, "Updated 1 pending auctions to active and 1 active auctions to closed")
    
    def test_update_auction_statuses_with_bids(self):
        """Test that winners are set correctly when closing auctions with bids"""
        # Add bids to the auction that should be closed
        bid1 = BidFactory(
            auction=self.active_to_closed,
            bidder=self.bidder1,
            amount=self.active_to_closed.current_price + 10
        )
        bid2 = BidFactory(
            auction=self.active_to_closed,
            bidder=self.bidder2,
            amount=self.active_to_closed.current_price + 20
        )
        
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            update_auction_statuses()
        
        # Get fresh data from database
        self.active_to_closed.refresh_from_db()
        
        # Assert the auction is closed and the winner is set correctly
        self.assertEqual(self.active_to_closed.status, 'closed')
        self.assertEqual(self.active_to_closed.winner, self.bidder2)
    
    def test_update_auction_statuses_no_bids(self):
        """Test that auctions are closed with no winner when there are no bids"""
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            update_auction_statuses()
        
        # Get fresh data from database
        self.active_to_closed.refresh_from_db()
        
        # Assert the auction is closed but has no winner
        self.assertEqual(self.active_to_closed.status, 'closed')
        self.assertIsNone(self.active_to_closed.winner)
    
    def test_update_auction_statuses_edge_case_no_changes(self):
        """Test behavior when no status changes are needed"""
        # Change statuses so no updates are needed
        self.pending_to_active.status = 'active'
        self.pending_to_active.save()
        self.active_to_closed.status = 'closed'
        self.active_to_closed.save()
        
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            result = update_auction_statuses()
        
        # Assert the result message indicates no auctions were updated
        self.assertEqual(result, "Updated 0 pending auctions to active and 0 active auctions to closed")
    
    def test_update_auction_statuses_multiple_transitions(self):
        """Test handling multiple status transitions at once"""
        # Create additional auctions that need status updates
        with patch('django.utils.timezone.now', return_value=self.now):
            second_pending_to_active = AuctionFactory(
                creator=self.seller,
                start_time=self.past - timedelta(minutes=30),
                end_time=self.future,
                status='pending'
            )
            
            second_active_to_closed = AuctionFactory(
                creator=self.seller,
                start_time=self.past - timedelta(days=3),
                end_time=self.past - timedelta(hours=2),
                status='active'
            )
        
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            result = update_auction_statuses()
        
        # Get fresh data from database
        second_pending_to_active.refresh_from_db()
        second_active_to_closed.refresh_from_db()
        
        # Assert the statuses are updated correctly
        self.assertEqual(second_pending_to_active.status, 'active')
        self.assertEqual(second_active_to_closed.status, 'closed')
        
        # Assert the result message is correct
        self.assertEqual(result, "Updated 2 pending auctions to active and 2 active auctions to closed")
    
    def test_update_auction_statuses_edge_case_instantaneous_transitions(self):
        """Test auction that should instantly transition from pending to closed"""
        # Create an auction with start time in the past and end time also in the past
        with patch('django.utils.timezone.now', return_value=self.now):
            instant_transition = AuctionFactory(
                creator=self.seller,
                start_time=self.past - timedelta(days=2),
                end_time=self.past,
                status='pending'  # This would normally be 'active' but we're testing edge case
            )
        
        # Run the task
        with patch('django.utils.timezone.now', return_value=self.now):
            update_auction_statuses()
        
        # Get fresh data from database
        instant_transition.refresh_from_db()
        
        # Assert the auction skipped 'active' and went straight to 'closed'
        self.assertEqual(instant_transition.status, 'closed')
    
    def test_update_auction_statuses_idempotence(self):
        """Test that running the task multiple times doesn't change results"""
        # Run the task once
        with patch('django.utils.timezone.now', return_value=self.now):
            update_auction_statuses()
        
        # Get fresh data after first run
        self.pending_to_active.refresh_from_db()
        self.active_to_closed.refresh_from_db()
        
        # Store the statuses
        status_after_first_run = {
            'pending_to_active': self.pending_to_active.status,
            'active_to_closed': self.active_to_closed.status,
        }
        
        # Run the task again
        with patch('django.utils.timezone.now', return_value=self.now):
            result = update_auction_statuses()
        
        # Get fresh data after second run
        self.pending_to_active.refresh_from_db()
        self.active_to_closed.refresh_from_db()
        
        # Assert the statuses haven't changed
        self.assertEqual(self.pending_to_active.status, status_after_first_run['pending_to_active'])
        self.assertEqual(self.active_to_closed.status, status_after_first_run['active_to_closed'])
        
        # Assert the result message indicates no changes
        self.assertEqual(result, "Updated 0 pending auctions to active and 0 active auctions to closed")
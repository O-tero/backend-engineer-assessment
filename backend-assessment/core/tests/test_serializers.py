from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory
from datetime import timedelta
import factory
import factory.fuzzy
from decimal import Decimal

from .models import Auction, Bid
from .serializers import (
    UserSerializer,
    BidSerializer,
    AuctionListSerializer,
    AuctionDetailSerializer,
    AuctionCreateSerializer
)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    password = factory.PostGenerationMethodCall('set_password', 'password123')


class AuctionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Auction

    title = factory.Faker('sentence', nb_words=5)
    description = factory.Faker('paragraph')
    starting_price = factory.fuzzy.FuzzyDecimal(10.00, 500.00, 2)
    current_price = factory.SelfAttribute('starting_price')
    creator = factory.SubFactory(UserFactory)
    start_time = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=1))
    end_time = factory.LazyFunction(lambda: timezone.now() + timedelta(days=3))
    status = 'pending'


class BidFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Bid

    auction = factory.SubFactory(AuctionFactory)
    bidder = factory.SubFactory(UserFactory)
    amount = factory.LazyAttribute(lambda o: o.auction.current_price + Decimal('10.00'))
    created_at = factory.LazyFunction(timezone.now)


class UserSerializerTestCase(TestCase):
    def test_user_create_with_valid_data(self):
        """Test creating a user with valid data."""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'securepassword123',
            'first_name': 'Test',
            'last_name': 'User'
        }
        serializer = UserSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertTrue(user.check_password('securepassword123'))

    def test_user_create_with_minimal_data(self):
        """Test creating a user with only required fields."""
        data = {
            'username': 'minimaluser',
            'password': 'securepassword123'
        }
        serializer = UserSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        
        self.assertEqual(user.username, 'minimaluser')
        self.assertEqual(user.email, '')
        self.assertEqual(user.first_name, '')
        self.assertEqual(user.last_name, '')

    def test_user_create_without_username(self):
        """Test creating a user without a username should fail."""
        data = {
            'email': 'test@example.com',
            'password': 'securepassword123'
        }
        serializer = UserSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)

    def test_user_create_without_password(self):
        """Test creating a user without a password should fail."""
        data = {
            'username': 'nopassworduser',
            'email': 'test@example.com'
        }
        serializer = UserSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_user_create_with_duplicate_username(self):
        """Test creating a user with a duplicate username should fail."""
        # Create first user
        UserFactory(username='duplicateuser')
        
        # Try to create another user with same username
        data = {
            'username': 'duplicateuser',
            'password': 'securepassword123'
        }
        serializer = UserSerializer(data=data)
        
        with self.assertRaises(Exception):
            serializer.is_valid(raise_exception=True)
            serializer.save()


class BidSerializerTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.creator = UserFactory()
        self.bidder = UserFactory()
        
        # Create an active auction
        now = timezone.now()
        self.active_auction = AuctionFactory(
            creator=self.creator,
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=1),
            starting_price=Decimal('100.00'),
            current_price=Decimal('100.00'),
            status='active'
        )
        
        # Create request context
        self.request = self.factory.post('/bids/')
        self.request.user = self.bidder

    def test_bid_create_with_valid_data(self):
        """Test creating a bid with valid data."""
        data = {
            'auction': self.active_auction.id,
            'amount': Decimal('150.00')
        }
        serializer = BidSerializer(data=data, context={'request': self.request})
        
        self.assertTrue(serializer.is_valid())
        bid = serializer.save()
        
        self.assertEqual(bid.auction, self.active_auction)
        self.assertEqual(bid.bidder, self.bidder)
        self.assertEqual(bid.amount, Decimal('150.00'))

    def test_bid_create_with_minimum_increment(self):
        """Test creating a bid with just above current price."""
        data = {
            'auction': self.active_auction.id,
            'amount': self.active_auction.current_price + Decimal('0.01')
        }
        serializer = BidSerializer(data=data, context={'request': self.request})
        
        self.assertTrue(serializer.is_valid())
        bid = serializer.save()
        
        self.assertEqual(bid.amount, self.active_auction.current_price + Decimal('0.01'))

    def test_bid_create_with_amount_equal_to_current_price(self):
        """Test creating a bid with amount equal to current price should fail."""
        data = {
            'auction': self.active_auction.id,
            'amount': self.active_auction.current_price
        }
        serializer = BidSerializer(data=data, context={'request': self.request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_bid_create_with_amount_less_than_current_price(self):
        """Test creating a bid with amount less than current price should fail."""
        data = {
            'auction': self.active_auction.id,
            'amount': self.active_auction.current_price - Decimal('10.00')
        }
        serializer = BidSerializer(data=data, context={'request': self.request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_bid_on_own_auction(self):
        """Test creating a bid on user's own auction should fail."""
        # Change request user to auction creator
        self.request.user = self.creator
        
        data = {
            'auction': self.active_auction.id,
            'amount': Decimal('150.00')
        }
        serializer = BidSerializer(data=data, context={'request': self.request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_bid_on_inactive_auction(self):
        """Test creating a bid on an inactive auction should fail."""
        # Create a pending auction
        pending_auction = AuctionFactory(
            creator=self.creator,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=2),
            status='pending'
        )
        
        data = {
            'auction': pending_auction.id,
            'amount': Decimal('150.00')
        }
        serializer = BidSerializer(data=data, context={'request': self.request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)


class AuctionListSerializerTestCase(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.auction = AuctionFactory(
            creator=self.user,
            starting_price=Decimal('100.00'),
            current_price=Decimal('150.00')
        )
        
        # Create some bids for the auction
        for _ in range(3):
            bidder = UserFactory()
            BidFactory(auction=self.auction, bidder=bidder)

    def test_auction_list_serialization(self):
        """Test serialization of an auction for list view."""
        serializer = AuctionListSerializer(self.auction)
        data = serializer.data
        
        self.assertEqual(data['id'], self.auction.id)
        self.assertEqual(data['title'], self.auction.title)
        self.assertEqual(Decimal(data['starting_price']), self.auction.starting_price)
        self.assertEqual(Decimal(data['current_price']), self.auction.current_price)
        self.assertEqual(data['creator_username'], self.user.username)
        self.assertEqual(data['status'], self.auction.status)
        self.assertEqual(data['bid_count'], 3)
        self.assertIn('time_left', data)

    def test_auction_list_time_left_pending(self):
        """Test time_left field for pending auction."""
        now = timezone.now()
        auction = AuctionFactory(
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=2),
            status='pending'
        )
        
        serializer = AuctionListSerializer(auction)
        self.assertEqual(serializer.data['time_left'], "Auction not started yet")

    def test_auction_list_time_left_active(self):
        """Test time_left field for active auction."""
        now = timezone.now()
        auction = AuctionFactory(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            status='active'
        )
        
        serializer = AuctionListSerializer(auction)
        self.assertIn('h', serializer.data['time_left'])
        self.assertIn('m', serializer.data['time_left'])

    def test_auction_list_time_left_closed(self):
        """Test time_left field for closed auction."""
        now = timezone.now()
        auction = AuctionFactory(
            start_time=now - timedelta(days=2),
            end_time=now - timedelta(days=1),
            status='closed'
        )
        
        serializer = AuctionListSerializer(auction)
        self.assertEqual(serializer.data['time_left'], "Auction closed")


class AuctionDetailSerializerTestCase(TestCase):
    def setUp(self):
        self.creator = UserFactory()
        self.bidder = UserFactory()
        self.auction = AuctionFactory(creator=self.creator)
        
        # Create some bids
        self.bid1 = BidFactory(auction=self.auction, bidder=self.bidder, amount=Decimal('120.00'))
        self.bid2 = BidFactory(auction=self.auction, bidder=UserFactory(), amount=Decimal('130.00'))
        
        # Update current price to match highest bid
        self.auction.current_price = Decimal('130.00')
        self.auction.save()

    def test_auction_detail_serialization(self):
        """Test serialization of an auction for detail view."""
        serializer = AuctionDetailSerializer(self.auction)
        data = serializer.data
        
        self.assertEqual(data['id'], self.auction.id)
        self.assertEqual(data['title'], self.auction.title)
        self.assertEqual(data['description'], self.auction.description)
        self.assertEqual(Decimal(data['starting_price']), self.auction.starting_price)
        self.assertEqual(Decimal(data['current_price']), self.auction.current_price)
        self.assertEqual(data['creator_username'], self.creator.username)
        self.assertEqual(data['status'], self.auction.status)
        self.assertEqual(data['bid_count'], 2)
        self.assertIn('time_left', data)
        
        # Check that bids are included
        self.assertEqual(len(data['bids']), 2)
        self.assertEqual(Decimal(data['bids'][0]['amount']), Decimal('130.00'))
        self.assertEqual(Decimal(data['bids'][1]['amount']), Decimal('120.00'))

    def test_auction_detail_with_winner(self):
        """Test serialization of a closed auction with a winner."""
        now = timezone.now()
        closed_auction = AuctionFactory(
            creator=self.creator,
            start_time=now - timedelta(days=2),
            end_time=now - timedelta(days=1),
            status='closed',
            winner=self.bidder
        )
        
        serializer = AuctionDetailSerializer(closed_auction)
        data = serializer.data
        
        self.assertEqual(data['winner'], self.bidder.id)
        self.assertEqual(data['winner_username'], self.bidder.username)

    def test_auction_detail_without_winner(self):
        """Test serialization of an auction without a winner."""
        serializer = AuctionDetailSerializer(self.auction)
        data = serializer.data
        
        self.assertIsNone(data['winner'])
        self.assertIsNone(data['winner_username'])


class AuctionCreateSerializerTestCase(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.factory = APIRequestFactory()
        self.request = self.factory.post('/auctions/')
        self.request.user = self.user
        self.now = timezone.now()
        
        self.valid_data = {
            'title': 'Test Auction',
            'description': 'This is a test auction',
            'starting_price': Decimal('100.00'),
            'start_time': self.now + timedelta(hours=1),
            'end_time': self.now + timedelta(days=1)
        }

    def test_auction_create_with_valid_data(self):
        """Test creating an auction with valid data."""
        serializer = AuctionCreateSerializer(data=self.valid_data, context={'request': self.request})
        
        self.assertTrue(serializer.is_valid())
        auction = serializer.save()
        
        self.assertEqual(auction.title, 'Test Auction')
        self.assertEqual(auction.description, 'This is a test auction')
        self.assertEqual(auction.starting_price, Decimal('100.00'))
        self.assertEqual(auction.current_price, Decimal('100.00'))
        self.assertEqual(auction.creator, self.user)
        self.assertEqual(auction.status, 'pending')

    def test_auction_create_with_minimal_data(self):
        """Test creating an auction with minimal required data."""
        data = {
            'title': 'Minimal Auction',
            'description': '',  # Empty description
            'starting_price': Decimal('1.00'),  # Minimum price
            'start_time': self.now + timedelta(hours=1),
            'end_time': self.now + timedelta(hours=2)
        }
        serializer = AuctionCreateSerializer(data=data, context={'request': self.request})
        
        self.assertTrue(serializer.is_valid())
        auction = serializer.save()
        
        self.assertEqual(auction.title, 'Minimal Auction')
        self.assertEqual(auction.description, '')
        self.assertEqual(auction.starting_price, Decimal('1.00'))
        self.assertEqual(auction.current_price, Decimal('1.00'))

    def test_auction_create_with_start_time_in_past(self):
        """Test creating an auction with start time in past should fail."""
        data = self.valid_data.copy()
        data['start_time'] = self.now - timedelta(hours=1)
        
        serializer = AuctionCreateSerializer(data=data, context={'request': self.request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_auction_create_with_end_time_before_start_time(self):
        """Test creating an auction with end time before start time should fail."""
        data = self.valid_data.copy()
        data['start_time'] = self.now + timedelta(days=2)
        data['end_time'] = self.now + timedelta(days=1)
        
        serializer = AuctionCreateSerializer(data=data, context={'request': self.request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_auction_create_with_end_time_equal_to_start_time(self):
        """Test creating an auction with end time equal to start time should fail."""
        same_time = self.now + timedelta(hours=1)
        data = self.valid_data.copy()
        data['start_time'] = same_time
        data['end_time'] = same_time
        
        serializer = AuctionCreateSerializer(data=data, context={'request': self.request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_auction_create_with_negative_price(self):
        """Test creating an auction with negative price should fail."""
        data = self.valid_data.copy()
        data['starting_price'] = Decimal('-10.00')
        
        serializer = AuctionCreateSerializer(data=data, context={'request': self.request})
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('starting_price', serializer.errors)

    def test_auction_create_with_immediate_start(self):
        """Test creating an auction that starts immediately."""
        data = self.valid_data.copy()
        data['start_time'] = self.now + timedelta(seconds=10)  # Almost immediate start
        
        serializer = AuctionCreateSerializer(data=data, context={'request': self.request})
        
        self.assertTrue(serializer.is_valid())
        auction = serializer.save()
        
        self.assertEqual(auction.status, 'pending')  # Should still be pending until exact start time

    def test_auction_create_status_setting(self):
        """Test status is properly set based on start/end times."""
        # Create a serializer with context
        context = {'request': self.request}
        
        # Case 1: Future start time
        data = self.valid_data.copy()
        serializer = AuctionCreateSerializer(data=data, context=context)
        serializer.is_valid()
        auction = serializer.save()
        self.assertEqual(auction.status, 'pending')
        
        # Case 2: Start time now, end time future
        data = self.valid_data.copy()
        data['start_time'] = self.now
        serializer = AuctionCreateSerializer(data=data, context=context)
        serializer.is_valid()
        auction = serializer.save()
        self.assertEqual(auction.status, 'active')
import json
from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

import factory
from factory.django import DjangoModelFactory

from .models import Auction, Bid


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'password123')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_staff = False


class AuctionFactory(DjangoModelFactory):
    class Meta:
        model = Auction

    title = factory.Faker('sentence', nb_words=5)
    description = factory.Faker('paragraph', nb_sentences=3)
    starting_price = factory.LazyFunction(lambda: Decimal('10.00'))
    current_price = factory.LazyFunction(lambda: Decimal('10.00'))
    creator = factory.SubFactory(UserFactory)
    start_time = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=1))
    end_time = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
    status = 'pending'
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)
    winner = None


class BidFactory(DjangoModelFactory):
    class Meta:
        model = Bid

    auction = factory.SubFactory(AuctionFactory)
    bidder = factory.SubFactory(UserFactory)
    amount = factory.LazyFunction(lambda: Decimal('15.00'))
    created_at = factory.LazyFunction(timezone.now)


class UserViewSetTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = UserFactory(username='admin', is_staff=True)
        self.regular_user = UserFactory(username='regular')
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'securepassword123',
            'first_name': 'Test',
            'last_name': 'User'
        }
        self.url = reverse('user-list')

    def test_user_registration_success(self):
        """Test user registration with valid data"""
        response = self.client.post(self.url, self.user_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 3)  # admin + regular + new user
        self.assertEqual(User.objects.filter(username='testuser').exists(), True)
        
        # Password should not be returned in response
        self.assertNotIn('password', response.data)
        
        # Verify user can be authenticated with the password
        user = User.objects.get(username='testuser')
        self.assertTrue(user.check_password('securepassword123'))

    def test_user_registration_missing_fields(self):
        """Test user registration with missing required fields"""
        # Missing username
        incomplete_data = self.user_data.copy()
        del incomplete_data['username']
        response = self.client.post(self.url, incomplete_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing password
        incomplete_data = self.user_data.copy()
        del incomplete_data['password']
        response = self.client.post(self.url, incomplete_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_registration_duplicate_username(self):
        """Test user registration with already existing username"""
        duplicate_data = self.user_data.copy()
        duplicate_data['username'] = 'regular'  # Username that already exists
        
        response = self.client.post(self.url, duplicate_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    def test_user_list_unauthenticated(self):
        """Test that unauthenticated users cannot list users"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_list_authenticated_regular(self):
        """Test that regular users can only see their own profile"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['username'], 'regular')

    def test_user_list_authenticated_admin(self):
        """Test that admin users can see all profiles"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # admin + regular user

    def test_user_detail_own_profile(self):
        """Test that users can view their own profile"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('user-detail', kwargs={'pk': self.regular_user.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'regular')

    def test_user_detail_other_profile_regular_user(self):
        """Test that regular users cannot view other profiles"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('user-detail', kwargs={'pk': self.admin_user.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_detail_other_profile_admin(self):
        """Test that admin users can view other profiles"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('user-detail', kwargs={'pk': self.regular_user.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'regular')

    def test_user_update_own_profile(self):
        """Test that users can update their own profile"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('user-detail', kwargs={'pk': self.regular_user.id})
        update_data = {'first_name': 'Updated', 'last_name': 'Name'}
        response = self.client.patch(url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Updated')
        self.assertEqual(response.data['last_name'], 'Name')
        
        # Verify database was updated
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.first_name, 'Updated')
        self.assertEqual(self.regular_user.last_name, 'Name')

    def test_user_update_other_profile_regular_user(self):
        """Test that regular users cannot update other profiles"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('user-detail', kwargs={'pk': self.admin_user.id})
        update_data = {'first_name': 'Hacked'}
        response = self.client.patch(url, update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Verify database was not updated
        self.admin_user.refresh_from_db()
        self.assertNotEqual(self.admin_user.first_name, 'Hacked')

    def test_user_delete_own_profile(self):
        """Test that users can delete their own profile"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('user-detail', kwargs={'pk': self.regular_user.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.regular_user.id).exists())

    def test_user_delete_other_profile_regular_user(self):
        """Test that regular users cannot delete other profiles"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('user-detail', kwargs={'pk': self.admin_user.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(User.objects.filter(id=self.admin_user.id).exists())


class AuctionViewSetTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = UserFactory(username='user1')
        self.user2 = UserFactory(username='user2')
        self.admin_user = UserFactory(username='admin', is_staff=True)
        
        # Create auctions with different statuses
        self.now = timezone.now()
        
        # Pending auction (starts in future)
        self.pending_auction = AuctionFactory(
            creator=self.user1,
            start_time=self.now + timedelta(hours=1),
            end_time=self.now + timedelta(days=7),
            status='pending'
        )
        
        # Active auction (already started but not ended)
        self.active_auction = AuctionFactory(
            creator=self.user1,
            start_time=self.now - timedelta(hours=1),
            end_time=self.now + timedelta(days=3),
            status='active'
        )
        
        # Closed auction (already ended)
        self.closed_auction = AuctionFactory(
            creator=self.user1,
            start_time=self.now - timedelta(days=7),
            end_time=self.now - timedelta(days=1),
            status='closed',
            winner=self.user2
        )
        
        # User2's auction
        self.user2_auction = AuctionFactory(
            creator=self.user2,
            start_time=self.now - timedelta(hours=2),
            end_time=self.now + timedelta(days=5),
            status='active'
        )
        
        self.auction_data = {
            'title': 'New Test Auction',
            'description': 'This is a test auction description',
            'starting_price': '50.00',
            'start_time': (self.now + timedelta(hours=2)).isoformat(),
            'end_time': (self.now + timedelta(days=5)).isoformat()
        }
        
        self.list_url = reverse('auction-list')

    def test_list_auctions_unauthenticated(self):
        """Test that unauthenticated users cannot list auctions"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_auctions_authenticated(self):
        """Test that authenticated users can list all auctions"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)  # All 4 auctions from setUp

    def test_filter_auctions_by_status(self):
        """Test filtering auctions by status"""
        self.client.force_authenticate(user=self.user1)
        
        # Test filtering active auctions
        response = self.client.get(f"{self.list_url}?status=active")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # active_auction + user2_auction
        
        # Test filtering pending auctions
        response = self.client.get(f"{self.list_url}?status=pending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # pending_auction
        
        # Test filtering closed auctions
        response = self.client.get(f"{self.list_url}?status=closed")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # closed_auction

    def test_filter_auctions_by_creator(self):
        """Test filtering auctions by creator"""
        self.client.force_authenticate(user=self.user1)
        
        # Test filtering by user1
        response = self.client.get(f"{self.list_url}?creator={self.user1.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)  # pending_auction + active_auction + closed_auction
        
        # Test filtering by user2
        response = self.client.get(f"{self.list_url}?creator={self.user2.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # user2_auction

    def test_filter_my_auctions(self):
        """Test filtering to show only user's auctions"""
        self.client.force_authenticate(user=self.user1)
        
        response = self.client.get(f"{self.list_url}?my=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)  # pending_auction + active_auction + closed_auction
        
        # Switch to user2
        self.client.force_authenticate(user=self.user2)
        response = self.client.get(f"{self.list_url}?my=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # user2_auction

    def test_filter_won_auctions(self):
        """Test filtering to show only auctions won by user"""
        self.client.force_authenticate(user=self.user2)
        
        response = self.client.get(f"{self.list_url}?won=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # closed_auction (won by user2)
        
        # Switch to user1 who hasn't won any auctions
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f"{self.list_url}?won=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)  # No auctions won

    def test_create_auction_success(self):
        """Test creating an auction with valid data"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(self.list_url, self.auction_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Auction.objects.count(), 5)  # 4 from setUp + 1 new
        
        # Verify auction was created with correct attributes
        auction = Auction.objects.get(title='New Test Auction')
        self.assertEqual(auction.creator, self.user1)
        self.assertEqual(auction.status, 'pending')
        self.assertEqual(auction.current_price, Decimal('50.00'))

    def test_create_auction_unauthenticated(self):
        """Test that unauthenticated users cannot create auctions"""
        response = self.client.post(self.list_url, self.auction_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Auction.objects.count(), 4)  # Only the 4 from setUp

    def test_create_auction_invalid_dates(self):
        """Test creating an auction with invalid dates"""
        self.client.force_authenticate(user=self.user1)
        
        # End time before start time
        invalid_data = self.auction_data.copy()
        invalid_data['end_time'] = (self.now + timedelta(hours=1)).isoformat()
        invalid_data['start_time'] = (self.now + timedelta(hours=2)).isoformat()
        
        response = self.client.post(self.list_url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Start time in the past
        invalid_data = self.auction_data.copy()
        invalid_data['start_time'] = (self.now - timedelta(hours=1)).isoformat()
        
        response = self.client.post(self.list_url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_auction_missing_fields(self):
        """Test creating an auction with missing required fields"""
        self.client.force_authenticate(user=self.user1)
        
        required_fields = ['title', 'description', 'starting_price', 'start_time', 'end_time']
        for field in required_fields:
            invalid_data = self.auction_data.copy()
            del invalid_data[field]
            
            response = self.client.post(self.list_url, invalid_data, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn(field, response.data)

    def test_create_auction_negative_price(self):
        """Test creating an auction with a negative price"""
        self.client.force_authenticate(user=self.user1)
        
        invalid_data = self.auction_data.copy()
        invalid_data['starting_price'] = '-10.00'
        
        response = self.client.post(self.list_url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_auction_detail(self):
        """Test retrieving auction details"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('auction-detail', kwargs={'pk': self.active_auction.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.active_auction.id)
        self.assertEqual(response.data['title'], self.active_auction.title)
        self.assertEqual(response.data['creator_username'], 'user1')
        self.assertEqual(response.data['status'], 'active')

    def test_update_auction_owner(self):
        """Test that auction owner can update the auction"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('auction-detail', kwargs={'pk': self.pending_auction.id})
        
        update_data = {
            'title': 'Updated Auction Title',
            'description': 'Updated description'
        }
        
        response = self.client.patch(url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify auction was updated
        self.pending_auction.refresh_from_db()
        self.assertEqual(self.pending_auction.title, 'Updated Auction Title')
        self.assertEqual(self.pending_auction.description, 'Updated description')

    def test_update_auction_non_owner(self):
        """Test that non-owner cannot update the auction"""
        self.client.force_authenticate(user=self.user2)
        url = reverse('auction-detail', kwargs={'pk': self.pending_auction.id})
        
        update_data = {
            'title': 'Hacked Auction Title'
        }
        
        response = self.client.patch(url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify auction was not updated
        self.pending_auction.refresh_from_db()
        self.assertNotEqual(self.pending_auction.title, 'Hacked Auction Title')

    def test_update_auction_admin(self):
        """Test that admin can update any auction"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('auction-detail', kwargs={'pk': self.pending_auction.id})
        
        update_data = {
            'title': 'Admin Updated Title'
        }
        
        response = self.client.patch(url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify auction was updated
        self.pending_auction.refresh_from_db()
        self.assertEqual(self.pending_auction.title, 'Admin Updated Title')

    def test_delete_auction_owner(self):
        """Test that auction owner can delete the auction"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('auction-detail', kwargs={'pk': self.pending_auction.id})
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify auction was deleted
        self.assertFalse(Auction.objects.filter(id=self.pending_auction.id).exists())

    def test_delete_auction_non_owner(self):
        """Test that non-owner cannot delete the auction"""
        self.client.force_authenticate(user=self.user2)
        url = reverse('auction-detail', kwargs={'pk': self.pending_auction.id})
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify auction was not deleted
        self.assertTrue(Auction.objects.filter(id=self.pending_auction.id).exists())

    def test_delete_auction_admin(self):
        """Test that admin can delete any auction"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('auction-detail', kwargs={'pk': self.pending_auction.id})
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify auction was deleted
        self.assertFalse(Auction.objects.filter(id=self.pending_auction.id).exists())

    def test_get_auction_bids(self):
        """Test retrieving bids for an auction"""
        # Create some bids
        bid1 = BidFactory(auction=self.active_auction, bidder=self.user2, amount=Decimal('15.00'))
        bid2 = BidFactory(auction=self.active_auction, bidder=self.user2, amount=Decimal('20.00'))
        
        self.client.force_authenticate(user=self.user1)
        url = reverse('auction-bids', kwargs={'pk': self.active_auction.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Bids should be ordered by amount (highest first)
        self.assertEqual(Decimal(response.data[0]['amount']), bid2.amount)
        self.assertEqual(Decimal(response.data[1]['amount']), bid1.amount)

    def test_place_bid_success(self):
        """Test placing a valid bid on an active auction"""
        self.client.force_authenticate(user=self.user2)
        url = reverse('auction-place-bid', kwargs={'pk': self.active_auction.id})
        
        bid_data = {
            'amount': '25.00'
        }
        
        response = self.client.post(url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify bid was created
        self.assertEqual(self.active_auction.bids.count(), 1)
        
        # Verify auction price was updated
        self.active_auction.refresh_from_db()
        self.assertEqual(self.active_auction.current_price, Decimal('25.00'))

    def test_place_bid_on_own_auction(self):
        """Test that users cannot bid on their own auctions"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('auction-place-bid', kwargs={'pk': self.active_auction.id})
        
        bid_data = {
            'amount': '25.00'
        }
        
        response = self.client.post(url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify no bid was created
        self.assertEqual(self.active_auction.bids.count(), 0)

    def test_place_bid_inactive_auction(self):
        """Test that users cannot bid on inactive auctions"""
        self.client.force_authenticate(user=self.user2)
        
        # Try bidding on pending auction
        url = reverse('auction-place-bid', kwargs={'pk': self.pending_auction.id})
        bid_data = {'amount': '25.00'}
        response = self.client.post(url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Try bidding on closed auction
        url = reverse('auction-place-bid', kwargs={'pk': self.closed_auction.id})
        response = self.client.post(url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_place_bid_lower_than_current(self):
        """Test that bids must be higher than current price"""
        # First place a valid bid to raise the price
        self.client.force_authenticate(user=self.user2)
        url = reverse('auction-place-bid', kwargs={'pk': self.active_auction.id})
        
        valid_bid = {'amount': '20.00'}
        response = self.client.post(url, valid_bid, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Now try to place a lower bid
        lower_bid = {'amount': '15.00'}
        response = self.client.post(url, lower_bid, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify only one bid exists
        self.assertEqual(self.active_auction.bids.count(), 1)


class BidViewSetTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = UserFactory(username='user1')
        self.user2 = UserFactory(username='user2')
        self.admin_user = UserFactory(username='admin', is_staff=True)
        
        self.now = timezone.now()
        
        # Create an active auction
        self.auction = AuctionFactory(
            creator=self.user1,
            start_time=self.now - timedelta(hours=1),
            end_time=self.now + timedelta(days=3),
            status='active',
            current_price=Decimal('10.00')
        )
        
        # Create some bids
        self.bid1 = BidFactory(
            auction=self.auction,
            bidder=self.user2,
            amount=Decimal('15.00')
        )
        
        self.bid2 = BidFactory(
            auction=self.auction,
            bidder=self.user2,
            amount=Decimal('20.00')
        )
        
        # Create another auction for testing
        self.auction2 = AuctionFactory(
            creator=self.user2,
            start_time=self.now - timedelta(hours=2),
            end_time=self.now + timedelta(days=5),
            status='active'
        )
        
        self.bid3 = BidFactory(
            auction=self.auction2,
            bidder=self.user1,
            amount=Decimal('25.00')
        )
        
        self.list_url = reverse('bid-list')

    def test_list_bids_unauthenticated(self):
        """Test that unauthenticated users cannot list bids"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_bids_authenticated_regular_user(self):
        """Test that regular users can only see their own bids"""
        self.client.force_authenticate(user=self.user2)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Only user2's bids (bid1 + bid2)
        
        # Switch to user1
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # Only user1's bid (bid3)

    def test_list_bids_authenticated_admin(self):
        """Test that admin users can see all bids"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)  # All bids (bid1 + bid2 + bid3)

    def test_filter_bids_by_auction(self):
        """Test filtering bids by auction"""
        self.client.force_authenticate(user=self.user2)
        response = self.client.get(f"{self.list_url}?auction={self.auction.id}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Only bids for auction1 by user2
        
        # Switch to admin to verify filtering works with all bids visible
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f"{self.list_url}?auction={self.auction.id}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # All bids for auction1
        
        response = self.client.get(f"{self.list_url}?auction={self.auction2.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # All bids for auction2
        
    def test_retrieve_bid_own(self):
        """Test retrieving details of own bid"""
        self.client.force_authenticate(user=self.user2)
        url = reverse('bid-detail', kwargs={'pk': self.bid1.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.bid1.id)
        self.assertEqual(Decimal(response.data['amount']), self.bid1.amount)
        self.assertEqual(response.data['bidder'], self.user2.id)
        self.assertEqual(response.data['bidder_username'], self.user2.username)
        
    def test_retrieve_bid_other_user(self):
        """Test that regular users cannot retrieve other users' bids"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('bid-detail', kwargs={'pk': self.bid1.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
    def test_retrieve_bid_admin(self):
        """Test that admin users can retrieve any bid"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('bid-detail', kwargs={'pk': self.bid1.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.bid1.id)
        
    def test_create_bid_success(self):
        """Test creating a valid bid"""
        self.client.force_authenticate(user=self.user2)
        
        bid_data = {
            'auction': self.auction.id,
            'amount': '30.00'
        }
        
        response = self.client.post(self.list_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify bid was created
        self.assertEqual(Bid.objects.count(), 4)  # 3 from setUp + 1 new
        
        # Verify auction price was updated
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, Decimal('30.00'))
        
    def test_create_bid_on_own_auction(self):
        """Test that users cannot bid on their own auctions"""
        self.client.force_authenticate(user=self.user1)
        
        bid_data = {
            'auction': self.auction.id,
            'amount': '30.00'
        }
        
        response = self.client.post(self.list_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify no bid was created
        self.assertEqual(Bid.objects.count(), 3)  # Still only the 3 from setUp
        
    def test_create_bid_inactive_auction(self):
        """Test that users cannot bid on inactive auctions"""
        self.client.force_authenticate(user=self.user2)
        
        # Create a closed auction
        closed_auction = AuctionFactory(
            creator=self.user1,
            start_time=self.now - timedelta(days=7),
            end_time=self.now - timedelta(days=1),
            status='closed'
        )
        
        bid_data = {
            'auction': closed_auction.id,
            'amount': '30.00'
        }
        
        response = self.client.post(self.list_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify no bid was created
        self.assertEqual(Bid.objects.count(), 3)
        
    def test_create_bid_lower_than_current(self):
        """Test that bids must be higher than current price"""
        self.client.force_authenticate(user=self.user2)
        
        bid_data = {
            'auction': self.auction.id,
            'amount': '5.00'  # Lower than current price (20.00)
        }
        
        response = self.client.post(self.list_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify no new bid was created
        self.assertEqual(Bid.objects.count(), 3)
        
    def test_update_bid_not_allowed(self):
        """Test that even admin users cannot update bids"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('bid-detail', kwargs={'pk': self.bid1.id})
        
        update_data = {
            'amount': '50.00'
        }
        
        response = self.client.patch(url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        # Verify bid was not updated
        self.bid1.refresh_from_db()
        self.assertEqual(self.bid1.amount, Decimal('15.00'))
        
    def test_delete_bid_regular_user(self):
        """Test that regular users cannot delete bids"""
        self.client.force_authenticate(user=self.user2)
        url = reverse('bid-detail', kwargs={'pk': self.bid1.id})
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        # Verify bid was not deleted
        self.assertTrue(Bid.objects.filter(id=self.bid1.id).exists())
        
    def test_delete_bid_admin(self):
        """Test that admin users can delete bids"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('bid-detail', kwargs={'pk': self.bid1.id})
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify bid was deleted
        self.assertFalse(Bid.objects.filter(id=self.bid1.id).exists())
        
        # Verify auction price not affected (should still reflect highest remaining bid)
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, Decimal('20.00'))  # From bid2
        
        
class AuctionPermissionsTestCase(TestCase):
    """Test case focused specifically on permissions and edge cases for auction actions"""
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = UserFactory(username='user1')
        self.user2 = UserFactory(username='user2')
        self.admin_user = UserFactory(username='admin', is_staff=True)
        
        self.now = timezone.now()
        
        # Create auctions with different statuses
        self.active_auction = AuctionFactory(
            creator=self.user1,
            start_time=self.now - timedelta(hours=1),
            end_time=self.now + timedelta(days=3),
            status='active'
        )
        
    def test_auction_status_auto_update(self):
        """Test that auction status is automatically updated when saved"""
        # Create a pending auction
        auction = AuctionFactory(
            creator=self.user1,
            start_time=self.now + timedelta(hours=1),
            end_time=self.now + timedelta(days=3),
            status='pending'
        )
        
        # Manually change start_time to make it active
        auction.start_time = self.now - timedelta(minutes=10)
        auction.save()
        
        # Verify status was updated to active
        self.assertEqual(auction.status, 'active')
        
        # Manually change end_time to make it closed
        auction.end_time = self.now - timedelta(minutes=5)
        auction.save()
        
        # Verify status was updated to closed
        self.assertEqual(auction.status, 'closed')
        
    def test_update_auction_after_bids_placed(self):
        """Test updating an auction after bids have been placed"""
        # Place a bid
        bid = BidFactory(
            auction=self.active_auction,
            bidder=self.user2,
            amount=Decimal('15.00')
        )
        
        # Attempt to update the auction
        self.client.force_authenticate(user=self.user1)
        url = reverse('auction-detail', kwargs={'pk': self.active_auction.id})
        
        update_data = {
            'title': 'Updated Title',
            'description': 'Updated description'
        }
        
        response = self.client.patch(url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify auction was updated but price and bids remain
        self.active_auction.refresh_from_db()
        self.assertEqual(self.active_auction.title, 'Updated Title')
        self.assertEqual(self.active_auction.current_price, Decimal('15.00'))
        self.assertEqual(self.active_auction.bids.count(), 1)
        
    def test_search_auctions(self):
        """Test searching auctions by title and description"""
        # Create auctions with specific titles and descriptions
        auction1 = AuctionFactory(
            title="Vintage watch collection",
            description="Collection of rare timepieces",
            creator=self.user1,
            status='active'
        )
        
        auction2 = AuctionFactory(
            title="Modern furniture",
            description="Including a vintage-inspired chair",
            creator=self.user1,
            status='active'
        )
        
        self.client.force_authenticate(user=self.user1)
        
        # Search by title
        response = self.client.get(f"{reverse('auction-list')}?search=vintage")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], auction1.id)
        
        # Search by description
        response = self.client.get(f"{reverse('auction-list')}?search=vintage-inspired")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], auction2.id)
        
    def test_ordering_auctions(self):
        """Test ordering auctions by different fields"""
        # Create auctions with specific dates and prices
        auction1 = AuctionFactory(
            title="First auction",
            starting_price=Decimal('10.00'),
            current_price=Decimal('10.00'),
            creator=self.user1,
            created_at=self.now - timedelta(days=5),
            end_time=self.now + timedelta(days=1),
            status='active'
        )
        
        auction2 = AuctionFactory(
            title="Second auction",
            starting_price=Decimal('20.00'),
            current_price=Decimal('20.00'),
            creator=self.user1,
            created_at=self.now - timedelta(days=2),
            end_time=self.now + timedelta(days=5),
            status='active'
        )
        
        auction3 = AuctionFactory(
            title="Third auction",
            starting_price=Decimal('5.00'),
            current_price=Decimal('5.00'),
            creator=self.user1,
            created_at=self.now - timedelta(days=3),
            end_time=self.now + timedelta(days=3),
            status='active'
        )
        
        self.client.force_authenticate(user=self.user1)
        
        # Test ordering by created_at (default is descending)
        response = self.client.get(f"{reverse('auction-list')}?ordering=created_at")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)  # 3 new + 1 from setUp
        self.assertEqual(response.data[0]['title'], "First auction")
        self.assertEqual(response.data[1]['title'], "Third auction")
        self.assertEqual(response.data[2]['title'], "Second auction")
        
        # Test ordering by current_price ascending
        response = self.client.get(f"{reverse('auction-list')}?ordering=current_price")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['title'], "Third auction")
        self.assertEqual(response.data[1]['title'], "First auction")
        self.assertEqual(response.data[2]['title'], "Second auction")
        
        # Test ordering by end_time descending
        response = self.client.get(f"{reverse('auction-list')}?ordering=-end_time")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['title'], "Second auction")
        self.assertEqual(response.data[1]['title'], "Third auction")
        self.assertEqual(response.data[2]['title'], "First auction")
        
    def test_edge_case_time_validation(self):
        """Test edge cases for time validation in auctions"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('auction-list')
        
        # Test with start_time equal to end_time
        data = {
            'title': 'Edge Case Auction',
            'description': 'Testing time validation',
            'starting_price': '10.00',
            'start_time': self.now.isoformat(),
            'end_time': self.now.isoformat()
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test with very short auction duration (1 second)
        data = {
            'title': 'Short Auction',
            'description': 'Testing short duration',
            'starting_price': '10.00',
            'start_time': self.now.isoformat(),
            'end_time': (self.now + timedelta(seconds=1)).isoformat()
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        
class BidEdgeCasesTestCase(TestCase):
    """Test case focused specifically on bidding edge cases"""
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = UserFactory(username='user1')
        self.user2 = UserFactory(username='user2')
        self.user3 = UserFactory(username='user3')
        
        self.now = timezone.now()
        
        # Create an active auction
        self.auction = AuctionFactory(
            creator=self.user1,
            start_time=self.now - timedelta(hours=1),
            end_time=self.now + timedelta(days=3),
            status='active',
            starting_price=Decimal('10.00'),
            current_price=Decimal('10.00')
        )
        
        self.bid_url = reverse('auction-place-bid', kwargs={'pk': self.auction.id})
        
    def test_consecutive_bids_same_user(self):
        """Test placing consecutive bids by the same user"""
        self.client.force_authenticate(user=self.user2)
        
        # First bid
        bid_data = {'amount': '15.00'}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Second bid (higher)
        bid_data = {'amount': '20.00'}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify both bids were created and price updated
        self.assertEqual(self.auction.bids.count(), 2)
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, Decimal('20.00'))
        
    def test_concurrent_bids_different_users(self):
        """Test multiple users bidding on the same auction"""
        # User2 places a bid
        self.client.force_authenticate(user=self.user2)
        bid_data = {'amount': '15.00'}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # User3 places a higher bid
        self.client.force_authenticate(user=self.user3)
        bid_data = {'amount': '20.00'}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # User2 bids again
        self.client.force_authenticate(user=self.user2)
        bid_data = {'amount': '25.00'}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all bids were created and price updated to highest bid
        self.assertEqual(self.auction.bids.count(), 3)
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, Decimal('25.00'))
        
    def test_exact_decimal_precision(self):
        """Test bidding with exact decimal precision"""
        self.client.force_authenticate(user=self.user2)
        
        # Bid with max decimal precision (2 places)
        bid_data = {'amount': '15.99'}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, Decimal('15.99'))
        
        # Bid with too much decimal precision (truncated by Django)
        bid_data = {'amount': '20.999'}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, Decimal('21.00'))  # Rounded
        
    def test_bid_exactly_higher(self):
        """Test bidding exactly one cent higher than current price"""
        self.client.force_authenticate(user=self.user2)
        
        # Place an initial bid
        bid_data = {'amount': '15.00'}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Another user bids one cent higher
        self.client.force_authenticate(user=self.user3)
        bid_data = {'amount': '15.01'}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify both bids were created and price updated
        self.assertEqual(self.auction.bids.count(), 2)
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, Decimal('15.01'))
        
    def test_max_price_bid(self):
        """Test bidding with the maximum allowed price"""
        self.client.force_authenticate(user=self.user2)
        
        # Bid with maximum value allowed by DecimalField(max_digits=10, decimal_places=2)
        max_bid = '99999999.99'
        bid_data = {'amount': max_bid}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, Decimal(max_bid))
        
    def test_bid_equal_to_current_price(self):
        """Test bidding exactly equal to current price (should be rejected)"""
        self.client.force_authenticate(user=self.user2)
        
        # Place an initial bid
        bid_data = {'amount': '15.00'}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Another user tries to bid the same amount
        self.client.force_authenticate(user=self.user3)
        bid_data = {'amount': '15.00'}
        response = self.client.post(self.bid_url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify only the first bid was created
        self.assertEqual(self.auction.bids.count(), 1)
        
    def test_bid_at_last_second(self):
        """Test bidding right before auction closes"""
        # Create an auction that's about to end
        closing_auction = AuctionFactory(
            creator=self.user1,
            start_time=self.now - timedelta(days=6),
            end_time=self.now + timedelta(seconds=1),
            status='active',
            starting_price=Decimal('10.00'),
            current_price=Decimal('10.00')
        )
        
        self.client.force_authenticate(user=self.user2)
        url = reverse('auction-place-bid', kwargs={'pk': closing_auction.id})
        
        # Place bid right before closing
        bid_data = {'amount': '15.00'}
        response = self.client.post(url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify bid was accepted
        self.assertEqual(closing_auction.bids.count(), 1)
        closing_auction.refresh_from_db()
        self.assertEqual(closing_auction.current_price, Decimal('15.00'))
        
        # Wait for auction to close
        import time
        time.sleep(2)
        
        # Try to place another bid after closing
        self.client.force_authenticate(user=self.user3)
        bid_data = {'amount': '20.00'}
        response = self.client.post(url, bid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify auction is now closed and has the correct winner
        closing_auction.refresh_from_db()
        self.assertEqual(closing_auction.status, 'closed')
        self.assertEqual(closing_auction.winner, self.user2)
        
        
class PermissionsTestCase(TestCase):
    """Test case focused specifically on permissions across the API"""
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = UserFactory(username='user1')
        self.user2 = UserFactory(username='user2')
        self.admin_user = UserFactory(username='admin', is_staff=True)
        
        self.now = timezone.now()
        
        # Create an auction
        self.auction = AuctionFactory(
            creator=self.user1,
            start_time=self.now - timedelta(hours=1),
            end_time=self.now + timedelta(days=3),
            status='active'
        )
        
        # Create a bid
        self.bid = BidFactory(
            auction=self.auction,
            bidder=self.user2,
            amount=Decimal('15.00')
        )
        
    def test_anonymous_access(self):
        """Test that anonymous users cannot access protected endpoints"""
        # Try to access auction list
        response = self.client.get(reverse('auction-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Try to access auction detail
        response = self.client.get(reverse('auction-detail', kwargs={'pk': self.auction.id}))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Try to create an auction
        data = {
            'title': 'Anonymous Auction',
            'description': 'Test',
            'starting_price': '10.00',
            'start_time': self.now.isoformat(),
            'end_time': (self.now + timedelta(days=1)).isoformat()
        }
        response = self.client.post(reverse('auction-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Try to place a bid
        bid_data = {'amount': '20.00'}
        response = self.client.post(
            reverse('auction-place-bid', kwargs={'pk': self.auction.id}),
            bid_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_cross_user_permissions(self):
        """Test that users cannot modify other users' resources"""
        # User2 tries to update User1's auction
        self.client.force_authenticate(user=self.user2)
        url = reverse('auction-detail', kwargs={'pk': self.auction.id})
        update_data = {'title': 'Hacked Auction'}
        response = self.client.patch(url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # User2 tries to delete User1's auction
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # User1 tries to view User2's bid details
        self.client.force_authenticate(user=self.user1)
        url = reverse('bid-detail', kwargs={'pk': self.bid.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
    def test_admin_permissions(self):
        """Test that admin users have full access"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Admin can view any auction
        url = reverse('auction-detail', kwargs={'pk': self.auction.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from .models import Auction
from datetime import timedelta
from django.utils import timezone


class AuthenticationTests(APITestCase):
    def test_register_user(self):
        """
        Test user registration.
        """
        url = reverse('register')
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpassword123',
            'first_name': 'Test',
            'last_name': 'User'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().username, 'testuser')
        
    def test_login_user(self):
        """
        Test user login and token generation.
        """
        # Create a user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        
        # Login
        url = reverse('token_obtain_pair')
        data = {
            'username': 'testuser',
            'password': 'testpassword123'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        
    def test_unauthorized_access(self):
        """
        Test that unauthorized users cannot access protected endpoints.
        """
        url = reverse('auction-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_authorized_access(self):
        """
        Test that authorized users can access protected endpoints.
        """
        # Create a user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        
        # Login
        login_url = reverse('token_obtain_pair')
        login_data = {
            'username': 'testuser',
            'password': 'testpassword123'
        }
        login_response = self.client.post(login_url, login_data, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        
        # Access protected endpoint
        token = login_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        url = reverse('auction-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AuctionTests(APITestCase):
    def setUp(self):
        # Create test users
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='password123'
        )
        
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='password123'
        )
        
        # Get tokens for user1
        login_url = reverse('token_obtain_pair')
        login_data = {
            'username': 'user1',
            'password': 'password123'
        }
        login_response = self.client.post(login_url, login_data, format='json')
        self.token_user1 = login_response.data['access']
        
        # Get tokens for user2
        login_data = {
            'username': 'user2',
            'password': 'password123'
        }
        login_response = self.client.post(login_url, login_data, format='json')
        self.token_user2 = login_response.data['access']
        
    def test_create_auction(self):
        """
        Test creating an auction.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_user1}')
        url = reverse('auction-list')
        data = {
            'title': 'Test Auction',
            'description': 'This is a test auction',
            'starting_price': '100.00',
            'start_time': (timezone.now() + timedelta(hours=1)).isoformat(),
            'end_time': (timezone.now() + timedelta(days=1)).isoformat()
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Auction.objects.count(), 1)
        self.assertEqual(Auction.objects.get().title, 'Test Auction')
        
    def test_bidding_on_auction(self):
        """
        Test bidding on an auction.
        """
        # User1 creates an auction
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_user1}')
        auction_url = reverse('auction-list')
        auction_data = {
            'title': 'Test Auction',
            'description': 'This is a test auction',
            'starting_price': '100.00',
            'start_time': timezone.now().isoformat(),
            'end_time': (timezone.now() + timedelta(days=1)).isoformat()
        }
        auction_response = self.client.post(auction_url, auction_data, format='json')
        auction_id = auction_response.data['id']
        
        # User2 places a bid
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_user2}')
        bid_url = reverse('auction-place-bid', args=[auction_id])
        bid_data = {
            'amount': '150.00'
        }
        bid_response = self.client.post(bid_url, bid_data, format='json')
        self.assertEqual(bid_response.status_code, status.HTTP_200_OK)
        self.assertEqual(bid_response.data['current_price'], '150.00')
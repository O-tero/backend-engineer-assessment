from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Auction, Bid


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name']
        read_only_fields = ['id']
        
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user


class BidSerializer(serializers.ModelSerializer):
    bidder_username = serializers.ReadOnlyField(source='bidder.username')
    
    class Meta:
        model = Bid
        fields = ['id', 'auction', 'bidder', 'bidder_username', 'amount', 'created_at']
        read_only_fields = ['id', 'bidder', 'bidder_username', 'created_at']
    
    def validate(self, data):
        # The bidder is set in the view
        auction = data['auction']
        request = self.context.get('request')
        
        # Check if auction is active
        if not auction.is_active:
            raise serializers.ValidationError("This auction is not active")
        
        # Check if user is trying to bid on their own auction
        if auction.creator == request.user:
            raise serializers.ValidationError("You cannot bid on your own auction")
        
        # Check if bid amount is greater than current price
        if data['amount'] <= auction.current_price:
            raise serializers.ValidationError(
                f"Bid amount must be greater than current price (${auction.current_price})"
            )
        
        return data
    
    def create(self, validated_data):
        # Set the bidder to the current user
        validated_data['bidder'] = self.context['request'].user
        return super().create(validated_data)


class AuctionListSerializer(serializers.ModelSerializer):
    creator_username = serializers.ReadOnlyField(source='creator.username')
    bid_count = serializers.SerializerMethodField()
    time_left = serializers.SerializerMethodField()
    
    class Meta:
        model = Auction
        fields = [
            'id', 'title', 'starting_price', 'current_price', 'creator_username',
            'start_time', 'end_time', 'status', 'bid_count', 'time_left'
        ]
        read_only_fields = ['id', 'creator_username', 'current_price', 'status', 'bid_count', 'time_left']
    
    def get_bid_count(self, obj):
        return obj.bids.count()
    
    def get_time_left(self, obj):
        if obj.status == 'closed':
            return "Auction closed"
        elif obj.status == 'pending':
            return "Auction not started yet"
        
        now = timezone.now()
        if now >= obj.end_time:
            return "Auction ended"
            
        time_left = obj.end_time - now
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        else:
            return f"{minutes}m {seconds}s"


class AuctionDetailSerializer(serializers.ModelSerializer):
    creator_username = serializers.ReadOnlyField(source='creator.username')
    bids = BidSerializer(many=True, read_only=True)
    bid_count = serializers.SerializerMethodField()
    time_left = serializers.SerializerMethodField()
    winner_username = serializers.ReadOnlyField(source='winner.username', allow_null=True)
    
    class Meta:
        model = Auction
        fields = [
            'id', 'title', 'description', 'starting_price', 'current_price',
            'creator', 'creator_username', 'start_time', 'end_time', 'status',
            'created_at', 'updated_at', 'bids', 'bid_count', 'time_left',
            'winner', 'winner_username'
        ]
        read_only_fields = [
            'id', 'creator', 'creator_username', 'current_price', 'status',
            'created_at', 'updated_at', 'bids', 'bid_count', 'time_left',
            'winner', 'winner_username'
        ]
    
    def get_bid_count(self, obj):
        return obj.bids.count()
    
    def get_time_left(self, obj):
        if obj.status == 'closed':
            return "Auction closed"
        elif obj.status == 'pending':
            return "Auction not started yet"
        
        now = timezone.now()
        if now >= obj.end_time:
            return "Auction ended"
            
        time_left = obj.end_time - now
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        else:
            return f"{minutes}m {seconds}s"


class AuctionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Auction
        fields = ['id', 'title', 'description', 'starting_price', 'start_time', 'end_time']
        read_only_fields = ['id']
    
    def validate(self, data):
        # Validate that end_time is after start_time
        if data['end_time'] <= data['start_time']:
            raise serializers.ValidationError("End time must be after start time")
        
        # Validate that start_time is not in the past
        if data['start_time'] < timezone.now():
            raise serializers.ValidationError("Start time cannot be in the past")
            
        return data
    
    def create(self, validated_data):
        # Set the creator to the current user
        validated_data['creator'] = self.context['request'].user
        
        # Set current_price to starting_price initially
        validated_data['current_price'] = validated_data['starting_price']
        
        # Set initial status
        now = timezone.now()
        if validated_data['start_time'] <= now < validated_data['end_time']:
            validated_data['status'] = 'active'
        elif now >= validated_data['end_time']:
            validated_data['status'] = 'closed'
        else:
            validated_data['status'] = 'pending'
            
        return super().create(validated_data)
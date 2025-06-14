import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.cache import CacheService, cached, cache_invalidate, get_cache_service
from common.config import get_settings
from services.inventory.service import InventoryService
from services.notification.service import NotificationService


class TestCacheService:
    """Test the core CacheService functionality"""

    @pytest.fixture
    async def mock_redis(self):
        """Mock Redis client"""
        redis_mock = AsyncMock()
        redis_mock.ping = AsyncMock()
        redis_mock.get = AsyncMock()
        redis_mock.set = AsyncMock()
        redis_mock.setex = AsyncMock()
        redis_mock.delete = AsyncMock()
        redis_mock.keys = AsyncMock()
        redis_mock.info = AsyncMock()
        redis_mock.close = AsyncMock()
        return redis_mock

    @pytest.fixture
    async def cache_service(self, mock_redis):
        """Create a test cache service with mocked Redis"""
        with patch("common.cache.aioredis.from_url", return_value=mock_redis):
            cache = CacheService("test")
            await cache.initialize()
            return cache

    @pytest.mark.asyncio
    async def test_cache_initialization_success(self, mock_redis):
        """Test successful cache initialization"""
        with patch("common.cache.aioredis.from_url", return_value=mock_redis):
            cache = CacheService("test")
            await cache.initialize()

            assert cache.redis is not None
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_initialization_failure(self):
        """Test cache initialization failure gracefully handled"""
        with patch(
            "common.cache.aioredis.from_url", side_effect=Exception("Connection failed")
        ):
            cache = CacheService("test")
            await cache.initialize()

            assert cache.redis is None

    @pytest.mark.asyncio
    async def test_cache_disabled_by_config(self):
        """Test cache respects disabled configuration"""
        with patch("common.config.get_settings") as mock_settings:
            mock_settings.return_value.cache_enabled = False

            cache = CacheService("test")
            await cache.initialize()

            assert cache.redis is None

    @pytest.mark.asyncio
    async def test_cache_get_hit(self, cache_service):
        """Test cache hit scenario"""
        test_data = {"key": "value", "number": 123}
        cache_service.redis.get.return_value = json.dumps(test_data)

        result = await cache_service.get("test:key")

        assert result == test_data
        cache_service.redis.get.assert_called_once_with("test:key")

    @pytest.mark.asyncio
    async def test_cache_get_miss(self, cache_service):
        """Test cache miss scenario"""
        cache_service.redis.get.return_value = None

        result = await cache_service.get("test:key")

        assert result is None
        cache_service.redis.get.assert_called_once_with("test:key")

    @pytest.mark.asyncio
    async def test_cache_set_with_ttl(self, cache_service):
        """Test setting cache with TTL"""
        test_data = {"key": "value"}
        ttl = 300

        await cache_service.set("test:key", test_data, ttl)

        cache_service.redis.setex.assert_called_once()
        args = cache_service.redis.setex.call_args[0]
        assert args[0] == "test:key"
        assert args[1] == ttl
        assert json.loads(args[2]) == test_data

    @pytest.mark.asyncio
    async def test_cache_set_without_ttl(self, cache_service):
        """Test setting cache without TTL"""
        test_data = {"key": "value"}

        await cache_service.set("test:key", test_data)

        cache_service.redis.set.assert_called_once()
        args = cache_service.redis.set.call_args[0]
        assert args[0] == "test:key"
        assert json.loads(args[1]) == test_data

    @pytest.mark.asyncio
    async def test_cache_delete(self, cache_service):
        """Test cache deletion"""
        cache_service.redis.delete.return_value = 1

        result = await cache_service.delete("test:key")

        assert result is True
        cache_service.redis.delete.assert_called_once_with("test:key")

    @pytest.mark.asyncio
    async def test_cache_delete_pattern(self, cache_service):
        """Test cache pattern deletion"""
        cache_service.redis.keys.return_value = ["test:key1", "test:key2"]
        cache_service.redis.delete.return_value = 2

        result = await cache_service.delete_pattern("test:*")

        assert result == 2
        cache_service.redis.keys.assert_called_once_with("test:*")
        cache_service.redis.delete.assert_called_once_with("test:key1", "test:key2")

    def test_generate_key_simple(self):
        """Test cache key generation with simple arguments"""
        cache = CacheService("test")

        key = cache._generate_key("prefix", "arg1", "arg2")

        assert key == "test:prefix:arg1:arg2"

    def test_generate_key_with_kwargs(self):
        """Test cache key generation with keyword arguments"""
        cache = CacheService("test")

        key = cache._generate_key("prefix", "arg1", param1="value1", param2="value2")

        # Should include args and a hash of the kwargs
        parts = key.split(":")
        assert parts[0] == "test"
        assert parts[1] == "prefix"
        assert parts[2] == "arg1"
        assert len(parts[3]) == 8  # MD5 hash truncated to 8 chars

    @pytest.mark.asyncio
    async def test_cache_info(self, cache_service):
        """Test cache info retrieval"""
        cache_service.redis.info.return_value = {
            "used_memory_human": "1.5MB",
            "connected_clients": 5,
            "keyspace_hits": 100,
            "keyspace_misses": 20,
        }
        cache_service.redis.keys.return_value = ["test:key1", "test:key2"]

        info = await cache_service.get_cache_info()

        assert info["status"] == "active"
        assert info["service_keys"] == 2
        assert info["redis_memory_used"] == "1.5MB"


class TestCacheDecorators:
    """Test caching decorators"""

    @pytest.fixture
    async def mock_service(self):
        """Mock service with cache_service attribute"""
        service = MagicMock()
        service.cache_service = AsyncMock()
        service.cache_service.redis = True
        service.cache_service.settings = MagicMock()
        service.cache_service.settings.default_cache_ttl = 300
        service.cache_service._generate_key = MagicMock(return_value="test:key")
        service.cache_service.get = AsyncMock()
        service.cache_service.set = AsyncMock()
        service.cache_service.delete_pattern = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_cached_decorator_hit(self, mock_service):
        """Test cached decorator with cache hit"""
        mock_service.cache_service.get.return_value = {"cached": "data"}

        @cached("test_prefix")
        async def test_function(self, arg1):
            return {"original": "data"}

        result = await test_function(mock_service, "test_arg")

        assert result == {"cached": "data"}
        mock_service.cache_service.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_decorator_miss(self, mock_service):
        """Test cached decorator with cache miss"""
        mock_service.cache_service.get.return_value = None

        @cached("test_prefix")
        async def test_function(self, arg1):
            return {"original": "data"}

        result = await test_function(mock_service, "test_arg")

        assert result == {"original": "data"}
        mock_service.cache_service.get.assert_called_once()
        mock_service.cache_service.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_decorator_no_cache(self):
        """Test cached decorator when cache is not available"""
        service = MagicMock()
        service.cache_service = None

        @cached("test_prefix")
        async def test_function(self, arg1):
            return {"original": "data"}

        result = await test_function(service, "test_arg")

        # Should call original function directly
        assert result == {"original": "data"}

    @pytest.mark.asyncio
    async def test_cache_invalidate_decorator(self, mock_service):
        """Test cache invalidation decorator"""

        @cache_invalidate(["pattern1:*", "pattern2:*"])
        async def test_function(self, arg1):
            return {"result": "data"}

        result = await test_function(mock_service, "test_arg")

        assert result == {"result": "data"}
        # Should call delete_pattern for each pattern
        assert mock_service.cache_service.delete_pattern.call_count == 2


class TestInventoryServiceCaching:
    """Test caching in Inventory Service"""

    @pytest.fixture
    async def mock_inventory_service(self):
        """Mock inventory service with cache"""
        service = InventoryService()
        service.db = AsyncMock()
        service.cache_service = AsyncMock()
        service.cache_service.redis = True
        service.cache_service.settings = MagicMock()
        service.cache_service.settings.product_cache_ttl = 3600
        service.cache_service.settings.statistics_cache_ttl = 300
        service.cache_service._generate_key = MagicMock()
        service.cache_service.get = AsyncMock()
        service.cache_service.set = AsyncMock()
        service.cache_service.delete = AsyncMock()
        service.cache_service.delete_pattern = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_get_product_cache_hit(self, mock_inventory_service):
        """Test product retrieval with cache hit"""
        cached_product = {
            "product_id": "test-123",
            "name": "Test Product",
            "quantity": 50,
        }
        mock_inventory_service.cache_service.get.return_value = cached_product

        # Mock the cache key generation
        mock_inventory_service.cache_service._generate_key.return_value = (
            "inventory:product:test-123"
        )

        result = await mock_inventory_service.get_product("test-123")

        assert result == cached_product
        # Should not query database
        mock_inventory_service.db[
            mock_inventory_service.inventory_collection
        ].find_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_product_cache_miss(self, mock_inventory_service):
        """Test product retrieval with cache miss"""
        product_data = {
            "product_id": "test-123",
            "name": "Test Product",
            "quantity": 50,
        }

        # Cache miss
        mock_inventory_service.cache_service.get.return_value = None
        # Database return
        mock_inventory_service.db[
            mock_inventory_service.inventory_collection
        ].find_one = AsyncMock(return_value=product_data)

        result = await mock_inventory_service.get_product("test-123")

        assert result == product_data
        # Should query database and cache result
        mock_inventory_service.db[
            mock_inventory_service.inventory_collection
        ].find_one.assert_called_once()
        mock_inventory_service.cache_service.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_statistics_caching(self, mock_inventory_service):
        """Test statistics caching"""
        stats_data = {
            "total_products": 100,
            "low_stock_products": 5,
            "generated_at": datetime.now().isoformat(),
        }

        # Cache miss
        mock_inventory_service.cache_service.get.return_value = None

        # Mock database aggregation operations
        mock_inventory_service.db[
            mock_inventory_service.inventory_collection
        ].aggregate = AsyncMock()
        mock_inventory_service.db[
            mock_inventory_service.inventory_collection
        ].count_documents = AsyncMock(return_value=100)
        mock_inventory_service.db[
            mock_inventory_service.reservations_collection
        ].count_documents = AsyncMock(return_value=10)

        # Mock aggregation results
        async def mock_aggregate(pipeline):
            if "$group" in str(pipeline) and "_id" in str(pipeline):
                if "status" in str(pipeline):
                    # Status breakdown
                    return [
                        {
                            "_id": "available",
                            "count": 80,
                            "total_value": 8000,
                            "total_quantity": 400,
                            "total_reserved": 20,
                        }
                    ]
                else:
                    # Category breakdown
                    return [
                        {
                            "_id": "Electronics",
                            "count": 50,
                            "total_value": 5000,
                            "total_quantity": 200,
                        }
                    ]
            return []

        mock_inventory_service.db[
            mock_inventory_service.inventory_collection
        ].aggregate.side_effect = lambda x: mock_aggregate(x)

        result = await mock_inventory_service.get_inventory_statistics()

        # Should cache the result
        mock_inventory_service.cache_service.set.assert_called_once()
        assert "total_products" in result


class TestNotificationServiceCaching:
    """Test caching in Notification Service"""

    @pytest.fixture
    async def mock_notification_service(self):
        """Mock notification service with cache"""
        service = NotificationService()
        service.db = AsyncMock()
        service.cache_service = AsyncMock()
        service.cache_service.redis = True
        service.cache_service.settings = MagicMock()
        service.cache_service.settings.template_cache_ttl = 86400
        service.cache_service.settings.statistics_cache_ttl = 300
        service.cache_service._generate_key = MagicMock()
        service.cache_service.get = AsyncMock()
        service.cache_service.set = AsyncMock()
        service.cache_service.delete_pattern = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_get_template_cache_hit(self, mock_notification_service):
        """Test template retrieval with cache hit"""
        cached_template = {
            "template_id": "order_confirmation_email",
            "subject": "Order Confirmed",
            "body": "Your order {{order_id}} has been confirmed",
        }
        mock_notification_service.cache_service.get.return_value = cached_template

        result = await mock_notification_service.get_notification_template(
            "order_confirmation_email"
        )

        assert result == cached_template
        # Should not query database
        mock_notification_service.db[
            mock_notification_service.templates_collection
        ].find_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_template_cache_miss(self, mock_notification_service):
        """Test template retrieval with cache miss"""
        template_data = {
            "template_id": "order_confirmation_email",
            "subject": "Order Confirmed",
            "body": "Your order {{order_id}} has been confirmed",
        }

        # Cache miss
        mock_notification_service.cache_service.get.return_value = None
        # Database return
        mock_notification_service.db[
            mock_notification_service.templates_collection
        ].find_one = AsyncMock(return_value=template_data)

        result = await mock_notification_service.get_notification_template(
            "order_confirmation_email"
        )

        assert result == template_data
        # Should query database and cache result
        mock_notification_service.db[
            mock_notification_service.templates_collection
        ].find_one.assert_called_once()
        mock_notification_service.cache_service.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_invalidates_cache(self, mock_notification_service):
        """Test that sending notification invalidates statistics cache"""
        notification_data = {
            "notification_type": "order_confirmation",
            "customer_id": "cust-123",
            "order_id": "order-456",
            "channels": ["email"],
        }

        # Mock database operations
        mock_notification_service.db[
            mock_notification_service.notifications_collection
        ].insert_one = AsyncMock()
        mock_notification_service._simulate_notification_sending = MagicMock(
            return_value=True
        )

        result = await mock_notification_service.send_notification(notification_data)

        # Should invalidate statistics cache
        mock_notification_service.cache_service.delete_pattern.assert_called()


class TestCacheIntegration:
    """Integration tests for caching across services"""

    @pytest.mark.asyncio
    async def test_cache_service_isolation(self):
        """Test that different services have isolated cache namespaces"""
        with patch("common.cache.aioredis.from_url") as mock_redis_factory:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_redis_factory.return_value = mock_redis

            inventory_cache = await get_cache_service("inventory")
            notification_cache = await get_cache_service("notification")

            assert inventory_cache.service_name == "inventory"
            assert notification_cache.service_name == "notification"

            # Keys should be namespaced
            inv_key = inventory_cache._generate_key("product", "123")
            notif_key = notification_cache._generate_key("template", "email")

            assert inv_key.startswith("inventory:")
            assert notif_key.startswith("notification:")

    @pytest.mark.asyncio
    async def test_cache_performance_monitoring(self):
        """Test cache performance monitoring"""
        with patch("common.cache.aioredis.from_url") as mock_redis_factory:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_redis.info.return_value = {
                "used_memory_human": "2.1MB",
                "connected_clients": 3,
                "keyspace_hits": 150,
                "keyspace_misses": 25,
            }
            mock_redis.keys.return_value = [
                "inventory:product:1",
                "inventory:product:2",
            ]
            mock_redis_factory.return_value = mock_redis

            cache = await get_cache_service("inventory")
            info = await cache.get_cache_info()

            assert info["status"] == "active"
            assert info["service_keys"] == 2
            assert info["redis_memory_used"] == "2.1MB"
            assert info["redis_keyspace_hits"] == 150

    @pytest.mark.asyncio
    async def test_datetime_serialization(self):
        """Test that datetime objects are properly serialized in cache"""
        with patch("common.cache.aioredis.from_url") as mock_redis_factory:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_redis_factory.return_value = mock_redis

            cache = await get_cache_service("test")

            test_data = {
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "name": "Test Product",
            }

            await cache.set("test:key", test_data, 300)

            # Should not raise serialization error
            mock_redis.setex.assert_called_once()

            # Check that datetime was converted to ISO string
            stored_data = mock_redis.setex.call_args[0][2]
            parsed_data = json.loads(stored_data)
            assert isinstance(parsed_data["created_at"], str)
            assert "T" in parsed_data["created_at"]  # ISO format


if __name__ == "__main__":
    pytest.main([__file__])

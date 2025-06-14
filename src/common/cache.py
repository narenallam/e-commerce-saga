import json
import hashlib
import asyncio
from typing import Any, Optional, Dict, Callable, Union
from functools import wraps
from datetime import datetime, timedelta
import logging

# Use modern Redis async client (Python 3.11 compatible)
try:
    import redis.asyncio as aioredis
    from redis.asyncio import Redis

    REDIS_AVAILABLE = True
except ImportError:
    # Mock Redis for graceful degradation
    class Redis:
        pass

    aioredis = None
    REDIS_AVAILABLE = False

from .config import get_settings


class CacheService:
    """Redis-based caching service with advanced features"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.settings = get_settings(service_name)
        self.redis: Optional[Redis] = None
        self.logger = logging.getLogger(f"cache.{service_name}")

    async def initialize(self):
        """Initialize Redis connection"""
        if not REDIS_AVAILABLE:
            self.logger.info("Redis not available - caching disabled")
            return

        if not self.settings.cache_enabled:
            self.logger.info("Caching disabled by configuration")
            return

        try:
            self.redis = aioredis.from_url(
                self.settings.redis_url,
                db=self.settings.redis_db,
                max_connections=self.settings.redis_max_connections,
                socket_timeout=self.settings.redis_socket_timeout,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Test connection
            await self.redis.ping()
            self.logger.info(f"Redis cache initialized for {self.service_name}")

        except Exception as e:
            self.logger.error(f"Failed to initialize Redis cache: {e}")
            self.redis = None

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            self.logger.info(f"Redis connection closed for {self.service_name}")

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and parameters"""
        key_parts = [self.service_name, prefix]

        # Add positional arguments
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(
                    hashlib.md5(json.dumps(arg, sort_keys=True).encode()).hexdigest()[
                        :8
                    ]
                )
            else:
                key_parts.append(str(arg))

        # Add keyword arguments
        if kwargs:
            kwargs_str = json.dumps(kwargs, sort_keys=True)
            key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest()[:8])

        return ":".join(key_parts)

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis:
            return None

        try:
            value = await self.redis.get(key)
            if value:
                data = json.loads(value)
                self.logger.debug(f"Cache HIT: {key}")
                return data
            else:
                self.logger.debug(f"Cache MISS: {key}")
                return None
        except Exception as e:
            self.logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL"""
        if not self.redis:
            return False

        try:
            # Convert datetime objects to ISO strings for JSON serialization
            def datetime_handler(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            json_value = json.dumps(value, default=datetime_handler)

            if ttl:
                await self.redis.setex(key, ttl, json_value)
            else:
                await self.redis.set(key, json_value)

            self.logger.debug(f"Cache SET: {key} (TTL: {ttl})")
            return True

        except Exception as e:
            self.logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.redis:
            return False

        try:
            result = await self.redis.delete(key)
            if result:
                self.logger.debug(f"Cache DELETE: {key}")
            return bool(result)
        except Exception as e:
            self.logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.redis:
            return 0

        try:
            keys = await self.redis.keys(pattern)
            if keys:
                result = await self.redis.delete(*keys)
                self.logger.info(
                    f"Cache DELETE PATTERN: {pattern} - {result} keys deleted"
                )
                return result
            return 0
        except Exception as e:
            self.logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return 0

    async def clear_service_cache(self) -> int:
        """Clear all cache entries for this service"""
        pattern = f"{self.service_name}:*"
        return await self.delete_pattern(pattern)

    async def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics and info"""
        if not self.redis:
            return {"status": "disabled"}

        try:
            info = await self.redis.info()
            keys = await self.redis.keys(f"{self.service_name}:*")

            return {
                "status": "active",
                "service_keys": len(keys),
                "redis_memory_used": info.get("used_memory_human"),
                "redis_connected_clients": info.get("connected_clients"),
                "redis_keyspace_hits": info.get("keyspace_hits"),
                "redis_keyspace_misses": info.get("keyspace_misses"),
            }
        except Exception as e:
            self.logger.error(f"Error getting cache info: {e}")
            return {"status": "error", "error": str(e)}


def cached(
    prefix: str,
    ttl: Optional[int] = None,
    key_pattern: Optional[str] = None,
    invalidate_on: Optional[list] = None,
):
    """
    Decorator for caching function results

    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds (uses service default if None)
        key_pattern: Custom key pattern (e.g., "product:{product_id}")
        invalidate_on: List of cache keys to invalidate when this function is called
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get cache service from the instance
            cache_service = getattr(self, "cache_service", None)
            if not cache_service or not cache_service.redis:
                # No cache available, call function directly
                return await func(self, *args, **kwargs)

            # Generate cache key
            if key_pattern:
                # Use custom key pattern
                key = key_pattern.format(*args, **kwargs)
                key = f"{cache_service.service_name}:{key}"
            else:
                # Use automatic key generation
                key = cache_service._generate_key(prefix, *args, **kwargs)

            # Try to get from cache
            cached_result = await cache_service.get(key)
            if cached_result is not None:
                return cached_result

            # Call original function
            result = await func(self, *args, **kwargs)

            # Cache the result
            cache_ttl = ttl or cache_service.settings.default_cache_ttl
            await cache_service.set(key, result, cache_ttl)

            # Invalidate related keys if specified
            if invalidate_on:
                for invalidate_key in invalidate_on:
                    await cache_service.delete_pattern(
                        f"{cache_service.service_name}:{invalidate_key}"
                    )

            return result

        return wrapper

    return decorator


def cache_invalidate(patterns: list):
    """
    Decorator to invalidate cache patterns after function execution

    Args:
        patterns: List of cache key patterns to invalidate
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Call original function
            result = await func(self, *args, **kwargs)

            # Invalidate cache patterns
            cache_service = getattr(self, "cache_service", None)
            if cache_service and cache_service.redis:
                for pattern in patterns:
                    formatted_pattern = f"{cache_service.service_name}:{pattern}"
                    await cache_service.delete_pattern(formatted_pattern)
                    cache_service.logger.info(
                        f"Invalidated cache pattern: {formatted_pattern}"
                    )

            return result

        return wrapper

    return decorator


# Global cache instances for each service
_cache_instances: Dict[str, CacheService] = {}


async def get_cache_service(service_name: str) -> CacheService:
    """Get or create cache service instance for a service"""
    if service_name not in _cache_instances:
        cache_service = CacheService(service_name)
        await cache_service.initialize()
        _cache_instances[service_name] = cache_service

    return _cache_instances[service_name]


async def cleanup_cache_services():
    """Cleanup all cache service instances"""
    for cache_service in _cache_instances.values():
        await cache_service.close()
    _cache_instances.clear()

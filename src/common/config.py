from typing import Dict, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class ServiceSettings(BaseSettings):
    """Base settings for all services"""

    service_name: str
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "ecommerce_saga"
    log_level: str = "INFO"

    # Redis settings
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    redis_max_connections: int = 10
    redis_socket_timeout: int = 30

    # Cache settings
    cache_enabled: bool = True
    default_cache_ttl: int = 300  # 5 minutes default
    product_cache_ttl: int = 3600  # 1 hour for products
    statistics_cache_ttl: int = 300  # 5 minutes for statistics
    template_cache_ttl: int = 86400  # 24 hours for templates

    # Kafka settings for event-driven architecture
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_enable_auto_commit: bool = True
    kafka_auto_commit_interval_ms: int = 5000
    kafka_session_timeout_ms: int = 30000
    kafka_heartbeat_interval_ms: int = 3000
    kafka_max_poll_records: int = 500
    kafka_max_poll_interval_ms: int = 300000
    kafka_auto_offset_reset: str = "earliest"
    kafka_enable_idempotence: bool = True
    kafka_acks: str = "all"
    kafka_retries: int = 3
    kafka_batch_size: int = 16384
    kafka_linger_ms: int = 10
    kafka_buffer_memory: int = 33554432

    # Event-driven settings
    event_store_enabled: bool = True
    event_replay_enabled: bool = True
    saga_event_retention_days: int = 30
    event_processing_timeout_seconds: int = 60

    # Service URLs
    order_service_url: str = "http://order-service:8000"
    inventory_service_url: str = "http://inventory-service:8001"
    payment_service_url: str = "http://payment-service:8002"
    shipping_service_url: str = "http://shipping-service:8003"
    notification_service_url: str = "http://notification-service:8004"

    # Service ports
    order_service_port: int = 8000
    inventory_service_port: int = 8001
    payment_service_port: int = 8002
    shipping_service_port: int = 8003
    notification_service_port: int = 8004

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings(service_name: str) -> ServiceSettings:
    """Get cached settings for a service"""
    return ServiceSettings(service_name=service_name)


def get_service_urls() -> Dict[str, str]:
    """Get all service URLs"""
    settings = get_settings("common")
    return {
        "order": settings.order_service_url,
        "inventory": settings.inventory_service_url,
        "payment": settings.payment_service_url,
        "shipping": settings.shipping_service_url,
        "notification": settings.notification_service_url,
    }


def get_kafka_config() -> Dict[str, str]:
    """Get Kafka configuration"""
    settings = get_settings("common")
    return {
        "bootstrap_servers": settings.kafka_bootstrap_servers,
        "enable_auto_commit": settings.kafka_enable_auto_commit,
        "auto_commit_interval_ms": settings.kafka_auto_commit_interval_ms,
        "session_timeout_ms": settings.kafka_session_timeout_ms,
        "heartbeat_interval_ms": settings.kafka_heartbeat_interval_ms,
        "max_poll_records": settings.kafka_max_poll_records,
        "max_poll_interval_ms": settings.kafka_max_poll_interval_ms,
        "auto_offset_reset": settings.kafka_auto_offset_reset,
        "enable_idempotence": settings.kafka_enable_idempotence,
        "acks": settings.kafka_acks,
        "retries": settings.kafka_retries,
        "batch_size": settings.kafka_batch_size,
        "linger_ms": settings.kafka_linger_ms,
        "buffer_memory": settings.kafka_buffer_memory,
    }

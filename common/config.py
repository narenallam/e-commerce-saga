from typing import Dict, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class ServiceSettings(BaseSettings):
    """Base settings for all services"""

    service_name: str
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "ecommerce_saga"
    log_level: str = "INFO"

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

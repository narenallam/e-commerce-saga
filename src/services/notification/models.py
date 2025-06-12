from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import uuid


class NotificationType(str, Enum):
    ORDER_CONFIRMATION = "order_confirmation"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    SHIPPING_CONFIRMATION = "shipping_confirmation"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_DELIVERED = "order_delivered"
    ORDER_SHIPPED = "order_shipped"
    PAYMENT_FAILED = "payment_failed"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NotificationRequest(BaseModel):
    notification_type: NotificationType
    customer_id: str
    order_id: Optional[str] = None
    channels: List[NotificationChannel] = [NotificationChannel.EMAIL]
    data: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None


class NotificationResponse(BaseModel):
    notification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    notification_type: NotificationType
    customer_id: str
    order_id: Optional[str] = None
    channels: List[NotificationChannel]
    data: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None

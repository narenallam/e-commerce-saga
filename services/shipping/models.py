from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime, date
import uuid


class ShippingStatus(str, Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    PICKED_UP = "PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class ShippingMethod(str, Enum):
    STANDARD = "STANDARD"
    EXPRESS = "EXPRESS"
    OVERNIGHT = "OVERNIGHT"
    TWO_DAY = "TWO_DAY"
    INTERNATIONAL = "INTERNATIONAL"


class ShippingAddress(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str
    country: str
    address_type: str = "SHIPPING"


class ShippingScheduleRequest(BaseModel):
    order_id: str
    customer_id: str
    address: Dict[str, Any]
    items: List[Dict[str, Any]]
    method: ShippingMethod = ShippingMethod.STANDARD
    requested_delivery_date: Optional[date] = None
    special_instructions: Optional[str] = None


class ShippingResponse(BaseModel):
    shipping_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    customer_id: str
    address: Dict[str, Any]
    items: List[Dict[str, Any]]
    method: ShippingMethod
    status: ShippingStatus = ShippingStatus.PENDING
    tracking_number: Optional[str] = None
    estimated_delivery_date: Optional[date] = None
    requested_delivery_date: Optional[date] = None
    special_instructions: Optional[str] = None
    carrier: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ShippingCancelRequest(BaseModel):
    shipping_id: Optional[str] = None
    order_id: str
    reason: Optional[str] = None

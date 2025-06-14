from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class PaymentMethod(str, Enum):
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    PAYPAL = "PAYPAL"
    BANK_TRANSFER = "BANK_TRANSFER"


class ShippingMethod(str, Enum):
    STANDARD = "STANDARD"
    EXPRESS = "EXPRESS"
    OVERNIGHT = "OVERNIGHT"
    PICKUP = "PICKUP"


class OrderItem(BaseModel):
    product_id: str
    name: str
    sku: str = None
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    total_price: float = Field(..., gt=0)


class Address(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "US"
    address_type: str = "SHIPPING"


class OrderCreateRequest(BaseModel):
    customer_id: str
    items: List[OrderItem] = Field(..., min_items=1)
    total_amount: float = Field(..., gt=0)
    currency: str = "USD"
    shipping_address: Address
    billing_address: Optional[Address] = None
    payment_method: PaymentMethod
    shipping_method: ShippingMethod = ShippingMethod.STANDARD
    customer_details: Dict[str, Any] = {}


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    reason: Optional[str] = None
    updated_by: str = "system"


class Order(BaseModel):
    order_id: str
    customer_id: str
    items: List[OrderItem]
    total_amount: float
    currency: str = "USD"
    status: OrderStatus = OrderStatus.PENDING
    shipping_address: Address
    billing_address: Optional[Address] = None
    payment_method: PaymentMethod
    shipping_method: ShippingMethod
    order_date: datetime
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = {}


class OrderResponse(BaseModel):
    success: bool
    message: str
    order_id: Optional[str] = None
    order: Optional[Order] = None
    details: Dict[str, Any] = {}

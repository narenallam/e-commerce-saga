from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import uuid


class InventoryStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    DISCONTINUED = "DISCONTINUED"


class ProductInventory(BaseModel):
    product_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    sku: str
    quantity: int
    reserved_quantity: int = 0
    status: InventoryStatus = InventoryStatus.AVAILABLE
    price: float
    category: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class InventoryReservationRequest(BaseModel):
    product_id: str
    quantity: int
    order_id: str
    customer_id: str
    metadata: Optional[Dict[str, Any]] = None


class InventoryReservationResponse(BaseModel):
    reservation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str
    quantity: int
    order_id: str
    customer_id: str
    status: InventoryStatus
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class InventoryReleaseRequest(BaseModel):
    product_id: str
    quantity: int
    order_id: str
    customer_id: str
    reason: Optional[str] = None


class InventoryUpdateRequest(BaseModel):
    product_id: str
    quantity: Optional[int] = None
    status: Optional[InventoryStatus] = None
    price: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentMethod(str, Enum):
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    PAYPAL = "PAYPAL"
    BANK_TRANSFER = "BANK_TRANSFER"
    CRYPTO = "CRYPTO"


class CreditCardDetails(BaseModel):
    card_number_last4: str
    card_brand: str
    expiry_month: int
    expiry_year: int
    cardholder_name: str


class PaymentRequest(BaseModel):
    order_id: str
    amount: float
    currency: str = "USD"
    payment_method: PaymentMethod
    payment_details: Optional[Dict[str, Any]] = None
    customer_id: str


class PaymentResponse(BaseModel):
    payment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    amount: float
    currency: str
    payment_method: PaymentMethod
    payment_details: Optional[Dict[str, Any]] = None
    customer_id: str
    status: PaymentStatus = PaymentStatus.PENDING
    transaction_reference: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    error_message: Optional[str] = None


class RefundRequest(BaseModel):
    payment_id: Optional[str] = None
    order_id: str
    amount: Optional[float] = None  # If None, refund full amount
    reason: Optional[str] = None


class RefundResponse(BaseModel):
    refund_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payment_id: str
    order_id: str
    amount: float
    status: PaymentStatus = PaymentStatus.PROCESSING
    created_at: datetime = Field(default_factory=datetime.now)
    reason: Optional[str] = None

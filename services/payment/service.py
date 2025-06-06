import sys
import os
import uuid
import random
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add parent directory to path to import common modules
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from common.database import Database
from .models import PaymentStatus, PaymentMethod


class PaymentService:
    """Service for handling payment operations"""

    def __init__(self):
        self.payments_collection = "payments"
        self.refunds_collection = "refunds"
        self.db = None

    async def initialize(self):
        """Initialize the database connection"""
        self.db = await Database.connect("payment")

    async def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a payment for an order"""
        # Generate payment ID if not provided
        if "payment_id" not in payment_data:
            payment_data["payment_id"] = str(uuid.uuid4())

        # Set default values if not provided
        payment_data.setdefault("currency", "USD")
        payment_data.setdefault("status", PaymentStatus.PROCESSING.value)
        payment_data.setdefault("created_at", datetime.now())
        payment_data.setdefault("updated_at", datetime.now())

        # Try to get payment method from data
        payment_method = payment_data.get("payment_method")
        if not payment_method and "order_data" in payment_data:
            # Default payment method if not provided
            payment_method = PaymentMethod.CREDIT_CARD.value
            payment_data["payment_method"] = payment_method

        # Try to get amount from data
        if "amount" not in payment_data and "order_data" in payment_data:
            order_data = payment_data.get("order_data", {})
            payment_data["amount"] = order_data.get("total_amount", 0)

        # Try to get customer_id from data
        if "customer_id" not in payment_data and "order_data" in payment_data:
            order_data = payment_data.get("order_data", {})
            payment_data["customer_id"] = order_data.get("customer_id")

        # Try to get order_id from data
        if "order_id" not in payment_data and "order_data" in payment_data:
            order_data = payment_data.get("order_data", {})
            payment_data["order_id"] = order_data.get("order_id")

        # For demo purposes, simulate payment processing
        # In production, this would call a payment gateway API
        success = self._simulate_payment_processing()

        if success:
            payment_data["status"] = PaymentStatus.COMPLETED.value
            payment_data["transaction_reference"] = f"TX-{uuid.uuid4().hex[:8].upper()}"
        else:
            payment_data["status"] = PaymentStatus.FAILED.value
            payment_data["error_message"] = "Payment processing failed"

        # Update timestamp
        payment_data["updated_at"] = datetime.now()

        # Record payment in database
        await self.db[self.payments_collection].insert_one(payment_data)

        print(
            f"Payment processed: {payment_data['payment_id']} - Status: {payment_data['status']}"
        )

        # If payment failed, raise exception to trigger saga compensation
        if payment_data["status"] == PaymentStatus.FAILED.value:
            raise Exception(payment_data["error_message"])

        return payment_data

    def _simulate_payment_processing(self) -> bool:
        """Simulate payment processing with a high success rate"""
        # For demo purposes, succeed 90% of the time
        return random.random() <= 0.9

    async def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment by ID"""
        payment = await self.db[self.payments_collection].find_one(
            {"payment_id": payment_id}
        )
        return payment

    async def get_payment_by_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get payment by order ID"""
        payment = await self.db[self.payments_collection].find_one(
            {"order_id": order_id}
        )
        return payment

    async def refund_payment(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """Refund a payment"""
        # Get order ID
        order_id = refund_data.get("order_id")
        if not order_id:
            # Try to get order_id from original_response if available
            original_response = refund_data.get("original_response", {})
            order_id = original_response.get("order_id")

        if not order_id:
            raise ValueError("order_id is required for refund")

        # Get payment ID
        payment_id = refund_data.get("payment_id")

        # If payment_id not provided, look up by order_id
        if not payment_id:
            # Try to get payment_id from original_response if available
            original_response = refund_data.get("original_response", {})
            payment_id = original_response.get("payment_id")

        # If still no payment_id, look up by order_id
        if not payment_id:
            payment = await self.get_payment_by_order(order_id)
            if payment:
                payment_id = payment.get("payment_id")

        if not payment_id:
            # No payment found to refund
            return {
                "success": False,
                "message": f"No payment found for order_id: {order_id}",
            }

        # Get payment details
        payment = await self.get_payment(payment_id)
        if not payment:
            return {"success": False, "message": f"Payment {payment_id} not found"}

        # Check if payment can be refunded
        if payment.get("status") != PaymentStatus.COMPLETED.value:
            return {
                "success": False,
                "message": f"Payment {payment_id} cannot be refunded (status: {payment.get('status')})",
            }

        # Create refund record
        refund_id = str(uuid.uuid4())
        amount = refund_data.get("amount", payment.get("amount"))
        reason = refund_data.get("reason", "Order cancelled")

        refund = {
            "refund_id": refund_id,
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": amount,
            "status": PaymentStatus.PROCESSING.value,
            "reason": reason,
            "created_at": datetime.now(),
        }

        # For demo purposes, simulate refund processing
        # In production, this would call a payment gateway API
        refund["status"] = PaymentStatus.REFUNDED.value

        # Record refund in database
        await self.db[self.refunds_collection].insert_one(refund)

        # Update payment status
        await self.db[self.payments_collection].update_one(
            {"payment_id": payment_id},
            {
                "$set": {
                    "status": PaymentStatus.REFUNDED.value,
                    "updated_at": datetime.now(),
                }
            },
        )

        print(f"Payment refunded: {payment_id} - Refund ID: {refund_id}")

        return {
            "refund_id": refund_id,
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": amount,
            "status": PaymentStatus.REFUNDED.value,
            "success": True,
            "message": "Payment refunded successfully",
        }

    async def list_payments(
        self,
        customer_id: Optional[str] = None,
        status: Optional[PaymentStatus] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """List payments with optional filtering"""
        query = {}

        if customer_id:
            query["customer_id"] = customer_id

        if status:
            query["status"] = (
                status.value if isinstance(status, PaymentStatus) else status
            )

        cursor = self.db[self.payments_collection].find(query).skip(skip).limit(limit)
        payments = await cursor.to_list(length=limit)

        return payments

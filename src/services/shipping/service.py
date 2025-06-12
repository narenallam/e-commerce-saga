import sys
import os
import uuid
import random
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional

# Add parent directory to path to import common modules
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from common.database import Database
from .models import ShippingStatus, ShippingMethod


class ShippingService:
    """Service for handling shipping operations"""

    def __init__(self):
        self.shipments_collection = "shipments"
        self.db = None

    async def initialize(self):
        """Initialize the database connection"""
        self.db = await Database.connect("shipping")

    async def schedule_shipping(self, shipping_data: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule shipping for an order"""
        # Generate shipping ID if not provided
        if "shipping_id" not in shipping_data:
            shipping_data["shipping_id"] = str(uuid.uuid4())

        # Set default values if not provided
        shipping_data.setdefault("method", ShippingMethod.STANDARD.value)
        shipping_data.setdefault("status", ShippingStatus.PENDING.value)
        shipping_data.setdefault("created_at", datetime.now())
        shipping_data.setdefault("updated_at", datetime.now())

        # Try to get customer_id and address from data or order_data
        if "customer_id" not in shipping_data and "order_data" in shipping_data:
            order_data = shipping_data.get("order_data", {})
            shipping_data["customer_id"] = order_data.get("customer_id")

        if "address" not in shipping_data and "order_data" in shipping_data:
            order_data = shipping_data.get("order_data", {})
            shipping_data["address"] = order_data.get("shipping_address")

        # Try to get items from data or order_data
        if "items" not in shipping_data and "order_data" in shipping_data:
            order_data = shipping_data.get("order_data", {})
            shipping_data["items"] = order_data.get("items", [])

        # Try to get order_id from data
        if "order_id" not in shipping_data and "order_data" in shipping_data:
            order_data = shipping_data.get("order_data", {})
            shipping_data["order_id"] = order_data.get("order_id")

        # For demo purposes, simulate shipping scheduling
        # In production, this would call a shipping carrier API
        success = self._simulate_shipping_scheduling()

        if success:
            # Generate tracking number
            tracking_number = f"TRK{uuid.uuid4().hex[:12].upper()}"
            shipping_data["tracking_number"] = tracking_number

            # Assign carrier
            carriers = ["FedEx", "UPS", "USPS", "DHL"]
            shipping_data["carrier"] = random.choice(carriers)

            # Calculate estimated delivery date
            method = shipping_data.get("method")
            days_to_add = 5  # default for standard shipping

            if method == ShippingMethod.EXPRESS.value:
                days_to_add = 3
            elif method == ShippingMethod.OVERNIGHT.value:
                days_to_add = 1
            elif method == ShippingMethod.TWO_DAY.value:
                days_to_add = 2
            elif method == ShippingMethod.INTERNATIONAL.value:
                days_to_add = 10

            estimated_delivery = datetime.now() + timedelta(days=days_to_add)
            shipping_data["estimated_delivery_date"] = estimated_delivery.date()

            # Update status
            shipping_data["status"] = ShippingStatus.SCHEDULED.value
        else:
            shipping_data["status"] = ShippingStatus.FAILED.value
            shipping_data["error_message"] = "Failed to schedule shipping"

        # Update timestamp
        shipping_data["updated_at"] = datetime.now()

        # Record shipping in database
        await self.db[self.shipments_collection].insert_one(shipping_data)

        print(
            f"Shipping scheduled: {shipping_data['shipping_id']} - Status: {shipping_data['status']}"
        )

        # If shipping failed, raise exception to trigger saga compensation
        if shipping_data["status"] == ShippingStatus.FAILED.value:
            raise Exception(shipping_data["error_message"])

        return shipping_data

    def _simulate_shipping_scheduling(self) -> bool:
        """Simulate shipping scheduling with a high success rate"""
        # For demo purposes, succeed 95% of the time
        return random.random() <= 0.95

    async def get_shipping(self, shipping_id: str) -> Optional[Dict[str, Any]]:
        """Get shipping by ID"""
        shipping = await self.db[self.shipments_collection].find_one(
            {"shipping_id": shipping_id}
        )
        return shipping

    async def get_shipping_by_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get shipping by order ID"""
        shipping = await self.db[self.shipments_collection].find_one(
            {"order_id": order_id}
        )
        return shipping

    async def cancel_shipping(self, cancel_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a scheduled shipping"""
        # Get order ID
        order_id = cancel_data.get("order_id")
        if not order_id:
            # Try to get order_id from original_response if available
            original_response = cancel_data.get("original_response", {})
            order_id = original_response.get("order_id")

        if not order_id:
            raise ValueError("order_id is required for cancellation")

        # Get shipping ID
        shipping_id = cancel_data.get("shipping_id")

        # If shipping_id not provided, look up by order_id
        if not shipping_id:
            # Try to get shipping_id from original_response if available
            original_response = cancel_data.get("original_response", {})
            shipping_id = original_response.get("shipping_id")

        # If still no shipping_id, look up by order_id
        if not shipping_id:
            shipping = await self.get_shipping_by_order(order_id)
            if shipping:
                shipping_id = shipping.get("shipping_id")

        if not shipping_id:
            # No shipping found to cancel
            return {
                "success": False,
                "message": f"No shipping found for order_id: {order_id}",
            }

        # Get shipping details
        shipping = await self.get_shipping(shipping_id)
        if not shipping:
            return {"success": False, "message": f"Shipping {shipping_id} not found"}

        # Check if shipping can be cancelled
        if shipping.get("status") in [
            ShippingStatus.DELIVERED.value,
            ShippingStatus.CANCELLED.value,
        ]:
            return {
                "success": False,
                "message": f"Shipping {shipping_id} cannot be cancelled (status: {shipping.get('status')})",
            }

        # Update shipping status
        reason = cancel_data.get("reason", "Order cancelled")

        await self.db[self.shipments_collection].update_one(
            {"shipping_id": shipping_id},
            {
                "$set": {
                    "status": ShippingStatus.CANCELLED.value,
                    "updated_at": datetime.now(),
                    "cancellation_reason": reason,
                }
            },
        )

        print(f"Shipping cancelled: {shipping_id}")

        # Get updated shipping
        updated_shipping = await self.get_shipping(shipping_id)

        return {
            "shipping_id": shipping_id,
            "order_id": order_id,
            "status": ShippingStatus.CANCELLED.value,
            "success": True,
            "message": "Shipping cancelled successfully",
            "cancellation_reason": reason,
        }

    async def list_shipments(
        self,
        customer_id: Optional[str] = None,
        status: Optional[ShippingStatus] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """List shipments with optional filtering"""
        query = {}

        if customer_id:
            query["customer_id"] = customer_id

        if status:
            query["status"] = (
                status.value if isinstance(status, ShippingStatus) else status
            )

        cursor = self.db[self.shipments_collection].find(query).skip(skip).limit(limit)
        shipments = await cursor.to_list(length=limit)

        return shipments

    async def update_shipping_status(
        self,
        shipping_id: str,
        status: ShippingStatus,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update shipping status"""
        metadata = metadata or {}
        metadata["updated_at"] = datetime.now()

        result = await self.db[self.shipments_collection].update_one(
            {"shipping_id": shipping_id},
            {
                "$set": {
                    "status": (
                        status.value if isinstance(status, ShippingStatus) else status
                    ),
                    **metadata,
                }
            },
        )

        if result.modified_count == 0:
            return None

        return await self.get_shipping(shipping_id)

import sys
import os
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add parent directory to path to import common modules
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from common.database import Database
from .models import (
    ProductInventory,
    InventoryStatus,
    InventoryReservationRequest,
    InventoryReservationResponse,
    InventoryReleaseRequest,
    InventoryUpdateRequest,
)


class InventoryService:
    """Service for handling inventory operations"""

    def __init__(self):
        self.inventory_collection = "inventory"
        self.reservations_collection = "inventory_reservations"
        self.db = None

    async def initialize(self):
        """Initialize the database connection"""
        self.db = await Database.connect("inventory")

        # Create sample inventory if not exists
        if await self.db[self.inventory_collection].count_documents({}) == 0:
            await self._create_sample_inventory()

    async def _create_sample_inventory(self):
        """Create sample inventory items"""
        sample_items = [
            {
                "product_id": str(uuid.uuid4()),
                "name": "Laptop",
                "description": "High-performance laptop",
                "sku": "LAP-001",
                "quantity": 50,
                "reserved_quantity": 0,
                "status": InventoryStatus.AVAILABLE.value,
                "price": 999.99,
                "category": "Electronics",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
            {
                "product_id": str(uuid.uuid4()),
                "name": "Smartphone",
                "description": "Latest model smartphone",
                "sku": "PHN-001",
                "quantity": 100,
                "reserved_quantity": 0,
                "status": InventoryStatus.AVAILABLE.value,
                "price": 699.99,
                "category": "Electronics",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
        ]

        await self.db[self.inventory_collection].insert_many(sample_items)
        print("Sample inventory items created")

    async def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product by ID"""
        product = await self.db[self.inventory_collection].find_one(
            {"product_id": product_id}
        )
        return product

    async def list_products(
        self,
        category: Optional[str] = None,
        in_stock: Optional[bool] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """List products with optional filtering"""
        query = {}

        if category:
            query["category"] = category

        if in_stock is not None:
            if in_stock:
                query["quantity"] = {"$gt": 0}
            else:
                query["quantity"] = {"$lte": 0}

        cursor = self.db[self.inventory_collection].find(query).skip(skip).limit(limit)
        products = await cursor.to_list(length=limit)

        return products

    async def reserve_inventory(
        self, request: InventoryReservationRequest
    ) -> InventoryReservationResponse:
        """Reserve inventory items"""
        # Get product
        product = await self.get_product(request.product_id)
        if not product:
            raise ValueError(f"Product {request.product_id} not found")

        # Check if enough quantity is available
        available_quantity = product["quantity"] - product["reserved_quantity"]
        if available_quantity < request.quantity:
            raise ValueError(
                f"Not enough inventory available. Requested: {request.quantity}, Available: {available_quantity}"
            )

        # Create reservation
        reservation = {
            "reservation_id": str(uuid.uuid4()),
            "product_id": request.product_id,
            "quantity": request.quantity,
            "order_id": request.order_id,
            "customer_id": request.customer_id,
            "status": InventoryStatus.RESERVED.value,
            "created_at": datetime.now(),
            "metadata": request.metadata,
        }

        # Update product reserved quantity
        await self.db[self.inventory_collection].update_one(
            {"product_id": request.product_id},
            {
                "$inc": {"reserved_quantity": request.quantity},
                "$set": {"updated_at": datetime.now()},
            },
        )

        # Save reservation
        await self.db[self.reservations_collection].insert_one(reservation)

        return InventoryReservationResponse(**reservation)

    async def release_inventory(
        self, request: InventoryReleaseRequest
    ) -> Dict[str, Any]:
        """Release reserved inventory items"""
        # Find and delete reservation
        result = await self.db[self.reservations_collection].delete_one(
            {
                "product_id": request.product_id,
                "order_id": request.order_id,
                "customer_id": request.customer_id,
            }
        )

        if result.deleted_count == 0:
            return {
                "success": False,
                "message": "No matching reservation found",
            }

        # Update product reserved quantity
        await self.db[self.inventory_collection].update_one(
            {"product_id": request.product_id},
            {
                "$inc": {"reserved_quantity": -request.quantity},
                "$set": {"updated_at": datetime.now()},
            },
        )

        return {
            "success": True,
            "message": f"Released {request.quantity} items of product {request.product_id}",
        }

    async def update_inventory(
        self, request: InventoryUpdateRequest
    ) -> Optional[Dict[str, Any]]:
        """Update inventory item"""
        update_data = {}
        if request.quantity is not None:
            update_data["quantity"] = request.quantity
        if request.status is not None:
            update_data["status"] = request.status.value
        if request.price is not None:
            update_data["price"] = request.price
        if request.metadata is not None:
            update_data["metadata"] = request.metadata

        if not update_data:
            return None

        update_data["updated_at"] = datetime.now()

        result = await self.db[self.inventory_collection].update_one(
            {"product_id": request.product_id},
            {"$set": update_data},
        )

        if result.modified_count == 0:
            return None

        return await self.get_product(request.product_id)

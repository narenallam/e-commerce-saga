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
from common.cache import CacheService, cached, cache_invalidate, get_cache_service
from common.config import get_settings
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
        self.cache_service = None
        self.settings = get_settings("inventory")

    async def initialize(self):
        """Initialize the database connection and cache service"""
        self.db = await Database.connect("inventory")

        # Initialize cache service
        self.cache_service = await get_cache_service("inventory")

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

    @cached(
        prefix="product",
        ttl=None,  # Will use product_cache_ttl from settings (3600 seconds)
        key_pattern="product:{0}",  # Uses product_id as cache key
    )
    async def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product by ID (with Redis caching)"""
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

    @cache_invalidate(["product:*", "statistics:*"])
    async def reserve_inventory(
        self, request: InventoryReservationRequest
    ) -> InventoryReservationResponse:
        """Reserve inventory items (invalidates product and statistics cache)"""
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

    @cache_invalidate(["product:*", "statistics:*"])
    async def release_inventory(
        self, request: InventoryReleaseRequest
    ) -> Dict[str, Any]:
        """Release reserved inventory items (invalidates product and statistics cache)"""
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

    @cache_invalidate(["product:*", "statistics:*"])
    async def update_inventory(
        self, request: InventoryUpdateRequest
    ) -> Optional[Dict[str, Any]]:
        """Update inventory item (invalidates product and statistics cache)"""
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

        # Clear specific product cache
        if self.cache_service:
            await self.cache_service.delete(f"inventory:product:{request.product_id}")

        return await self.get_product(request.product_id)

    @cached(
        prefix="statistics",
        ttl=None,  # Will use statistics_cache_ttl from settings (300 seconds)
        key_pattern="statistics:all",
    )
    async def get_inventory_statistics(self) -> Dict[str, Any]:
        """Get inventory statistics (with Redis caching for 5-minute intervals)"""
        try:
            # Count products by status
            pipeline = [
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1},
                        "total_value": {"$sum": {"$multiply": ["$quantity", "$price"]}},
                        "total_quantity": {"$sum": "$quantity"},
                        "total_reserved": {"$sum": "$reserved_quantity"},
                    }
                }
            ]

            status_stats = []
            async for result in self.db[self.inventory_collection].aggregate(pipeline):
                status_stats.append(
                    {
                        "status": result["_id"],
                        "count": result["count"],
                        "total_value": result["total_value"],
                        "total_quantity": result["total_quantity"],
                        "total_reserved": result["total_reserved"],
                    }
                )

            # Total products count
            total_products = await self.db[self.inventory_collection].count_documents(
                {}
            )

            # Products with low stock (quantity < 10)
            low_stock_products = await self.db[
                self.inventory_collection
            ].count_documents({"quantity": {"$lt": 10}})

            # Out of stock products
            out_of_stock_products = await self.db[
                self.inventory_collection
            ].count_documents({"quantity": 0})

            # Category breakdown
            category_pipeline = [
                {
                    "$group": {
                        "_id": "$category",
                        "count": {"$sum": 1},
                        "total_value": {"$sum": {"$multiply": ["$quantity", "$price"]}},
                        "total_quantity": {"$sum": "$quantity"},
                    }
                }
            ]

            category_stats = []
            async for result in self.db[self.inventory_collection].aggregate(
                category_pipeline
            ):
                category_stats.append(
                    {
                        "category": result["_id"],
                        "count": result["count"],
                        "total_value": result["total_value"],
                        "total_quantity": result["total_quantity"],
                    }
                )

            # Recent reservations (last 7 days)
            from datetime import timedelta

            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_reservations = await self.db[
                self.reservations_collection
            ].count_documents({"created_at": {"$gte": seven_days_ago}})

            return {
                "total_products": total_products,
                "low_stock_products": low_stock_products,
                "out_of_stock_products": out_of_stock_products,
                "recent_reservations_7_days": recent_reservations,
                "status_breakdown": status_stats,
                "category_breakdown": category_stats,
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"Error getting inventory statistics: {str(e)}")
            return {"error": str(e)}

    # Saga-compatible methods (wrappers for main.py compatibility)
    async def list_inventory(
        self,
        status: Optional[InventoryStatus] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """List inventory with status filtering (saga-compatible wrapper)"""
        query = {}

        if status:
            query["status"] = status.value if hasattr(status, "value") else status

        cursor = self.db[self.inventory_collection].find(query).skip(skip).limit(limit)
        products = await cursor.to_list(length=limit)
        return products

    async def reserve_inventory(
        self, order_id: str, items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Reserve inventory for order items (saga-compatible)"""
        try:
            reservations = []
            failed_items = []

            for item in items:
                try:
                    product_id = item.get("product_id")
                    quantity = item.get("quantity", 1)

                    if not product_id:
                        failed_items.append(
                            {"item": item, "reason": "Missing product_id"}
                        )
                        continue

                    # Get product
                    product = await self.get_product(product_id)
                    if not product:
                        failed_items.append(
                            {"item": item, "reason": f"Product {product_id} not found"}
                        )
                        continue

                    # Check availability
                    available_quantity = product["quantity"] - product.get(
                        "reserved_quantity", 0
                    )
                    if available_quantity < quantity:
                        failed_items.append(
                            {
                                "item": item,
                                "reason": f"Insufficient stock. Available: {available_quantity}, Requested: {quantity}",
                            }
                        )
                        continue

                    # Create reservation
                    reservation_id = str(uuid.uuid4())
                    reservation = {
                        "reservation_id": reservation_id,
                        "product_id": product_id,
                        "quantity": quantity,
                        "order_id": order_id,
                        "status": InventoryStatus.RESERVED.value,
                        "created_at": datetime.now(),
                        "metadata": {"item_data": item},
                    }

                    # Update product reserved quantity
                    await self.db[self.inventory_collection].update_one(
                        {"product_id": product_id},
                        {
                            "$inc": {"reserved_quantity": quantity},
                            "$set": {"updated_at": datetime.now()},
                        },
                    )

                    # Save reservation
                    await self.db[self.reservations_collection].insert_one(reservation)
                    reservations.append(reservation)

                except Exception as e:
                    failed_items.append({"item": item, "reason": str(e)})

            if failed_items:
                return {
                    "success": False,
                    "message": "Some items could not be reserved",
                    "failed_items": failed_items,
                    "reservations": reservations,
                }

            return {
                "success": True,
                "message": f"Successfully reserved {len(reservations)} items",
                "order_id": order_id,
                "reservations": reservations,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to reserve inventory: {str(e)}",
                "failed_items": items,
            }

    async def release_inventory(
        self,
        order_id: str,
        reservation_id: Optional[str] = None,
        items: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Release reserved inventory (saga-compatible compensation)"""
        try:
            # Find reservations for this order
            query = {"order_id": order_id}
            if reservation_id:
                query["reservation_id"] = reservation_id

            reservations = (
                await self.db[self.reservations_collection].find(query).to_list(None)
            )

            if not reservations:
                return {
                    "success": True,  # Don't fail if no reservations found
                    "message": f"No reservations found for order {order_id}",
                }

            released_count = 0
            for reservation in reservations:
                try:
                    # Update product reserved quantity
                    await self.db[self.inventory_collection].update_one(
                        {"product_id": reservation["product_id"]},
                        {
                            "$inc": {"reserved_quantity": -reservation["quantity"]},
                            "$set": {"updated_at": datetime.now()},
                        },
                    )

                    # Delete reservation
                    await self.db[self.reservations_collection].delete_one(
                        {"reservation_id": reservation["reservation_id"]}
                    )

                    released_count += 1

                except Exception as e:
                    print(
                        f"Error releasing reservation {reservation['reservation_id']}: {str(e)}"
                    )

            return {
                "success": True,
                "message": f"Released {released_count} reservations for order {order_id}",
                "order_id": order_id,
                "released_count": released_count,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to release inventory: {str(e)}",
                "order_id": order_id,
            }

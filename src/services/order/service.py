import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from common.database import Database
from common.logging import setup_logging
from .models import (
    Order,
    OrderCreateRequest,
    OrderStatus,
    OrderStatusUpdate,
    OrderResponse,
)

logger = setup_logging("order-service")


class OrderService:
    def __init__(self):
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.collection_name = "orders"

    async def initialize(self):
        """Initialize the order service with database connection"""
        self.db = await Database.connect("order")
        logger.info("Order service initialized successfully")

    async def create_order(self, order_request: OrderCreateRequest) -> OrderResponse:
        """Create a new order"""
        try:
            order_id = str(uuid.uuid4())
            now = datetime.now()

            # Create order document
            order_data = {
                "order_id": order_id,
                "customer_id": order_request.customer_id,
                "items": [item.dict() for item in order_request.items],
                "total_amount": order_request.total_amount,
                "currency": order_request.currency,
                "status": OrderStatus.PENDING.value,
                "shipping_address": order_request.shipping_address.dict(),
                "billing_address": (
                    order_request.billing_address.dict()
                    if order_request.billing_address
                    else order_request.shipping_address.dict()
                ),
                "payment_method": order_request.payment_method.value,
                "shipping_method": order_request.shipping_method.value,
                "order_date": now,
                "created_at": now,
                "updated_at": now,
                "metadata": {
                    **order_request.customer_details,
                    "created_by": "api",
                },
            }

            # Insert order into database
            result = await self.db[self.collection_name].insert_one(order_data)

            if result.inserted_id:
                logger.info(f"Order created successfully: {order_id}")

                # Create Order object for response
                order_obj = Order(**order_data)

                return OrderResponse(
                    success=True,
                    message="Order created successfully",
                    order_id=order_id,
                    order=order_obj,
                    details={"inserted_id": str(result.inserted_id)},
                )
            else:
                logger.error(f"Failed to create order: {order_id}")
                return OrderResponse(
                    success=False,
                    message="Failed to create order",
                    details={"error": "Database insertion failed"},
                )

        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            return OrderResponse(
                success=False,
                message=f"Error creating order: {str(e)}",
                details={"error": str(e)},
            )

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        try:
            result = await self.db[self.collection_name].find_one(
                {"order_id": order_id}
            )

            if result:
                # Remove MongoDB's _id field
                result.pop("_id", None)
                return Order(**result)

            return None

        except Exception as e:
            logger.error(f"Error retrieving order {order_id}: {str(e)}")
            return None

    async def update_order_status(
        self, order_id: str, status_update: OrderStatusUpdate
    ) -> OrderResponse:
        """Update order status"""
        try:
            # Check if order exists
            existing_order = await self.get_order(order_id)
            if not existing_order:
                return OrderResponse(
                    success=False,
                    message=f"Order {order_id} not found",
                )

            # Update the order
            update_data = {
                "status": status_update.status.value,
                "updated_at": datetime.now(),
            }

            # Add status change reason to metadata
            if status_update.reason:
                update_data["metadata.status_change_reason"] = status_update.reason
                update_data["metadata.updated_by"] = status_update.updated_by

            result = await self.db[self.collection_name].update_one(
                {"order_id": order_id}, {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(
                    f"Order {order_id} status updated to {status_update.status.value}"
                )

                # Get updated order
                updated_order = await self.get_order(order_id)

                return OrderResponse(
                    success=True,
                    message=f"Order status updated to {status_update.status.value}",
                    order_id=order_id,
                    order=updated_order,
                )
            else:
                return OrderResponse(
                    success=False,
                    message="No changes made to order status",
                )

        except Exception as e:
            logger.error(f"Error updating order {order_id} status: {str(e)}")
            return OrderResponse(
                success=False,
                message=f"Error updating order status: {str(e)}",
                details={"error": str(e)},
            )

    async def cancel_order(
        self, order_id: str, reason: str = "User requested"
    ) -> OrderResponse:
        """Cancel an order"""
        try:
            existing_order = await self.get_order(order_id)
            if not existing_order:
                return OrderResponse(
                    success=False,
                    message=f"Order {order_id} not found",
                )

            # Check if order can be cancelled
            if existing_order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
                return OrderResponse(
                    success=False,
                    message=f"Cannot cancel order with status {existing_order.status}",
                )

            # Update status to cancelled
            status_update = OrderStatusUpdate(
                status=OrderStatus.CANCELLED,
                reason=reason,
                updated_by="api",
            )

            return await self.update_order_status(order_id, status_update)

        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {str(e)}")
            return OrderResponse(
                success=False,
                message=f"Error cancelling order: {str(e)}",
                details={"error": str(e)},
            )

    async def list_orders(
        self,
        customer_id: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Order]:
        """List orders with optional filtering"""
        try:
            # Build query filter
            query_filter = {}

            if customer_id:
                query_filter["customer_id"] = customer_id

            if status:
                query_filter["status"] = status.value

            # Execute query
            cursor = (
                self.db[self.collection_name]
                .find(query_filter)
                .sort("created_at", -1)  # Sort by newest first
                .skip(skip)
                .limit(limit)
            )

            results = await cursor.to_list(length=limit)

            # Convert to Order objects
            orders = []
            for result in results:
                result.pop("_id", None)  # Remove MongoDB's _id
                orders.append(Order(**result))

            logger.info(
                f"Retrieved {len(orders)} orders (customer_id={customer_id}, status={status})"
            )
            return orders

        except Exception as e:
            logger.error(f"Error listing orders: {str(e)}")
            return []

    async def get_order_statistics(self) -> Dict[str, Any]:
        """Get order statistics"""
        try:
            # Count orders by status
            pipeline = [
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1},
                        "total_amount": {"$sum": "$total_amount"},
                    }
                }
            ]

            status_stats = []
            async for result in self.db[self.collection_name].aggregate(pipeline):
                status_stats.append(
                    {
                        "status": result["_id"],
                        "count": result["count"],
                        "total_amount": result["total_amount"],
                    }
                )

            # Total orders count
            total_orders = await self.db[self.collection_name].count_documents({})

            # Recent orders (last 7 days)
            from datetime import timedelta

            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_orders = await self.db[self.collection_name].count_documents(
                {"created_at": {"$gte": seven_days_ago}}
            )

            return {
                "total_orders": total_orders,
                "recent_orders_7_days": recent_orders,
                "status_breakdown": status_stats,
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting order statistics: {str(e)}")
            return {"error": str(e)}

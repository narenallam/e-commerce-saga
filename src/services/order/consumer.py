import asyncio
import json
from typing import Dict, Any

from common.base_consumer import BaseServiceConsumer
from common.centralized_logging import get_logger
from .service import OrderService
from .models import OrderCreateRequest

logger = get_logger(__name__)


class OrderConsumer(BaseServiceConsumer):
    def __init__(self):
        self.order_service = OrderService()
        super().__init__("order", self.order_service)
        self.setup_service_handlers()

    async def setup_service_handlers(self):
        """Setup order service specific command and event handlers."""
        # Register order-specific saga commands
        self.register_command_handler("create_order", self._handle_create_order)
        self.register_command_handler("cancel_order", self._handle_cancel_order)
        self.register_command_handler(
            "update_order_status", self._handle_update_order_status
        )
        self.register_command_handler("get_order", self._handle_get_order)

        # Register event handlers for data consistency
        self.register_event_handler("payment_completed", self._handle_payment_completed)
        self.register_event_handler("payment_failed", self._handle_payment_failed)
        self.register_event_handler(
            "inventory_reserved", self._handle_inventory_reserved
        )
        self.register_event_handler(
            "inventory_reservation_failed", self._handle_inventory_reservation_failed
        )
        self.register_event_handler("shipping_created", self._handle_shipping_created)
        self.register_event_handler("shipping_failed", self._handle_shipping_failed)

    # Saga command handlers
    async def _handle_create_order(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle create order saga command."""
        try:
            # Extract order data from payload
            order_data = payload.get("order_data", payload)
            request_data = OrderCreateRequest(**order_data)

            # Create order
            result = await self.order_service.create_order(request_data)

            # Publish domain event for order creation
            if result.success:
                await self.publish_business_event(
                    event_type="order_created",
                    event_data={
                        "order_id": result.order_id,
                        "customer_id": request_data.customer_id,
                        "total_amount": request_data.total_amount,
                        "items": [item.dict() for item in request_data.items],
                    },
                    aggregate_id=result.order_id,
                )

            return result.dict()

        except Exception as e:
            # Publish domain event for order creation failure
            await self.publish_business_event(
                event_type="order_creation_failed",
                event_data={"error": str(e), "payload": payload},
            )
            raise

    async def _handle_cancel_order(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle cancel order saga command (compensation)."""
        try:
            order_id = payload.get("order_id")
            reason = payload.get("reason", "Saga compensation")

            if not order_id:
                raise ValueError("order_id is required for cancel_order command")

            result = await self.order_service.cancel_order(order_id, reason)

            # Publish domain event for order cancellation
            if result.success:
                await self.publish_business_event(
                    event_type="order_cancelled",
                    event_data={
                        "order_id": order_id,
                        "reason": reason,
                        "saga_id": message.get("saga_id"),
                    },
                    aggregate_id=order_id,
                )

            return result.dict()

        except Exception as e:
            await self.publish_business_event(
                event_type="order_cancellation_failed",
                event_data={"order_id": payload.get("order_id"), "error": str(e)},
            )
            raise

    async def _handle_update_order_status(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle update order status command."""
        try:
            order_id = payload.get("order_id")
            status = payload.get("status")
            reason = payload.get("reason", "Status update")

            if not all([order_id, status]):
                raise ValueError("order_id and status are required")

            from .models import OrderStatusUpdate, OrderStatus

            status_update = OrderStatusUpdate(
                status=OrderStatus(status), reason=reason, updated_by="saga"
            )

            result = await self.order_service.update_order_status(
                order_id, status_update
            )

            # Publish domain event for status update
            if result.success:
                await self.publish_business_event(
                    event_type="order_status_updated",
                    event_data={
                        "order_id": order_id,
                        "new_status": status,
                        "reason": reason,
                    },
                    aggregate_id=order_id,
                )

            return result.dict()

        except Exception as e:
            await self.publish_business_event(
                event_type="order_status_update_failed",
                event_data={"order_id": payload.get("order_id"), "error": str(e)},
            )
            raise

    async def _handle_get_order(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle get order command."""
        order_id = payload.get("order_id")
        if not order_id:
            raise ValueError("order_id is required for get_order command")

        order = await self.order_service.get_order(order_id)
        if order:
            return order.dict()
        else:
            raise ValueError(f"Order {order_id} not found")

    # Event handlers for data consistency
    async def _handle_payment_completed(self, event: Dict[str, Any]):
        """Handle payment completed event to update order status."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")

            if order_id:
                from .models import OrderStatusUpdate, OrderStatus

                status_update = OrderStatusUpdate(
                    status=OrderStatus.PROCESSING,
                    reason="Payment completed",
                    updated_by="payment-service",
                )
                await self.order_service.update_order_status(order_id, status_update)

        except Exception as e:
            logger.error(f"Error handling payment completed event: {e}")

    async def _handle_payment_failed(self, event: Dict[str, Any]):
        """Handle payment failed event to update order status."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")

            if order_id:
                from .models import OrderStatusUpdate, OrderStatus

                status_update = OrderStatusUpdate(
                    status=OrderStatus.CANCELLED,
                    reason="Payment failed",
                    updated_by="payment-service",
                )
                await self.order_service.update_order_status(order_id, status_update)

        except Exception as e:
            logger.error(f"Error handling payment failed event: {e}")

    async def _handle_inventory_reserved(self, event: Dict[str, Any]):
        """Handle inventory reserved event."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")

            if order_id:
                from .models import OrderStatusUpdate, OrderStatus

                status_update = OrderStatusUpdate(
                    status=OrderStatus.CONFIRMED,
                    reason="Inventory reserved",
                    updated_by="inventory-service",
                )
                await self.order_service.update_order_status(order_id, status_update)

        except Exception as e:
            logger.error(f"Error handling inventory reserved event: {e}")

    async def _handle_inventory_reservation_failed(self, event: Dict[str, Any]):
        """Handle inventory reservation failed event."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")

            if order_id:
                from .models import OrderStatusUpdate, OrderStatus

                status_update = OrderStatusUpdate(
                    status=OrderStatus.CANCELLED,
                    reason="Inventory reservation failed",
                    updated_by="inventory-service",
                )
                await self.order_service.update_order_status(order_id, status_update)

        except Exception as e:
            logger.error(f"Error handling inventory reservation failed event: {e}")

    async def _handle_shipping_created(self, event: Dict[str, Any]):
        """Handle shipping created event."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")

            if order_id:
                from .models import OrderStatusUpdate, OrderStatus

                status_update = OrderStatusUpdate(
                    status=OrderStatus.SHIPPED,
                    reason="Shipping created",
                    updated_by="shipping-service",
                )
                await self.order_service.update_order_status(order_id, status_update)

        except Exception as e:
            logger.error(f"Error handling shipping created event: {e}")

    async def _handle_shipping_failed(self, event: Dict[str, Any]):
        """Handle shipping failed event."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")

            if order_id:
                from .models import OrderStatusUpdate, OrderStatus

                status_update = OrderStatusUpdate(
                    status=OrderStatus.CANCELLED,
                    reason="Shipping failed",
                    updated_by="shipping-service",
                )
                await self.order_service.update_order_status(order_id, status_update)

        except Exception as e:
            logger.error(f"Error handling shipping failed event: {e}")


if __name__ == "__main__":
    consumer = OrderConsumer()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(consumer.start_consuming())
    except KeyboardInterrupt:
        print("Order Consumer shutting down...")
    finally:
        loop.run_until_complete(consumer.close())

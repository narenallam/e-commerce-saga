import asyncio
from typing import Dict, Any

from common.base_consumer import BaseServiceConsumer
from common.centralized_logging import get_logger
from .service import InventoryService
from .models import InventoryReservationRequest, InventoryUpdateRequest

logger = get_logger(__name__)


class InventoryConsumer(BaseServiceConsumer):
    def __init__(self):
        self.inventory_service = InventoryService()
        super().__init__("inventory", self.inventory_service)
        self.setup_service_handlers()

    async def setup_service_handlers(self):
        """Setup inventory service specific command and event handlers."""
        # Register inventory-specific saga commands
        self.register_command_handler(
            "reserve_inventory", self._handle_reserve_inventory
        )
        self.register_command_handler(
            "release_inventory", self._handle_release_inventory
        )
        self.register_command_handler("update_inventory", self._handle_update_inventory)
        self.register_command_handler(
            "check_availability", self._handle_check_availability
        )

        # Register event handlers for data consistency
        self.register_event_handler("order_created", self._handle_order_created)
        self.register_event_handler("order_cancelled", self._handle_order_cancelled)
        self.register_event_handler("payment_failed", self._handle_payment_failed)

    # Saga command handlers
    async def _handle_reserve_inventory(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle reserve inventory saga command."""
        try:
            # Extract reservation data
            order_id = payload.get("order_id")
            items = payload.get("items", [])

            if not order_id or not items:
                raise ValueError(
                    "order_id and items are required for reserve_inventory command"
                )

            # Create reservation request
            reservation_request = InventoryReservationRequest(
                order_id=order_id, items=items, reservation_type="order"
            )

            # Reserve inventory
            result = await self.inventory_service.reserve_inventory(reservation_request)

            # Publish domain event for inventory reservation
            if result.get("success", False):
                await self.publish_business_event(
                    event_type="inventory_reserved",
                    event_data={
                        "order_id": order_id,
                        "reservations": result.get("reservations", []),
                        "reserved_items": items,
                    },
                    aggregate_id=order_id,
                )
            else:
                await self.publish_business_event(
                    event_type="inventory_reservation_failed",
                    event_data={
                        "order_id": order_id,
                        "items": items,
                        "reason": result.get("message", "Unknown error"),
                    },
                    aggregate_id=order_id,
                )

            return result

        except Exception as e:
            # Publish domain event for reservation failure
            await self.publish_business_event(
                event_type="inventory_reservation_failed",
                event_data={
                    "order_id": payload.get("order_id"),
                    "error": str(e),
                    "items": payload.get("items", []),
                },
            )
            raise

    async def _handle_release_inventory(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle release inventory saga command (compensation)."""
        try:
            order_id = payload.get("order_id")
            reservations = payload.get("reservations", [])

            if not order_id:
                raise ValueError("order_id is required for release_inventory command")

            # Release inventory reservations
            result = await self.inventory_service.release_inventory(
                order_id, reservations
            )

            # Publish domain event for inventory release
            if result.get("success", False):
                await self.publish_business_event(
                    event_type="inventory_released",
                    event_data={
                        "order_id": order_id,
                        "released_reservations": reservations,
                        "saga_id": message.get("saga_id"),
                    },
                    aggregate_id=order_id,
                )

            return result

        except Exception as e:
            await self.publish_business_event(
                event_type="inventory_release_failed",
                event_data={"order_id": payload.get("order_id"), "error": str(e)},
            )
            raise

    async def _handle_update_inventory(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle update inventory command."""
        try:
            product_id = payload.get("product_id")
            quantity_change = payload.get("quantity_change")
            operation = payload.get("operation", "add")

            if not all([product_id, quantity_change is not None]):
                raise ValueError("product_id and quantity_change are required")

            update_request = InventoryUpdateRequest(
                product_id=product_id,
                quantity_change=quantity_change,
                operation=operation,
                reason=payload.get("reason", "Manual update"),
            )

            result = await self.inventory_service.update_inventory(update_request)

            # Publish domain event for inventory update
            if result.get("success", False):
                await self.publish_business_event(
                    event_type="inventory_updated",
                    event_data={
                        "product_id": product_id,
                        "quantity_change": quantity_change,
                        "operation": operation,
                        "new_quantity": result.get("new_quantity"),
                    },
                    aggregate_id=product_id,
                )

            return result

        except Exception as e:
            await self.publish_business_event(
                event_type="inventory_update_failed",
                event_data={"product_id": payload.get("product_id"), "error": str(e)},
            )
            raise

    async def _handle_check_availability(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle check availability command."""
        items = payload.get("items", [])
        if not items:
            raise ValueError("items are required for check_availability command")

        result = await self.inventory_service.check_availability(items)
        return result

    # Event handlers for data consistency
    async def _handle_order_created(self, event: Dict[str, Any]):
        """Handle order created event to check inventory availability."""
        try:
            event_data = event.get("event_data", {})
            items = event_data.get("items", [])
            order_id = event_data.get("order_id")

            if items and order_id:
                # Check availability and publish event
                availability = await self.inventory_service.check_availability(items)

                await self.publish_business_event(
                    event_type="inventory_availability_checked",
                    event_data={
                        "order_id": order_id,
                        "availability": availability,
                        "items": items,
                    },
                    aggregate_id=order_id,
                )

        except Exception as e:
            logger.error(f"Error handling order created event: {e}")

    async def _handle_order_cancelled(self, event: Dict[str, Any]):
        """Handle order cancelled event to release inventory."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")

            if order_id:
                # Auto-release any reservations for this order
                result = await self.inventory_service.release_inventory(order_id)

                if result.get("success", False):
                    await self.publish_business_event(
                        event_type="inventory_auto_released",
                        event_data={"order_id": order_id, "reason": "Order cancelled"},
                        aggregate_id=order_id,
                    )

        except Exception as e:
            logger.error(f"Error handling order cancelled event: {e}")

    async def _handle_payment_failed(self, event: Dict[str, Any]):
        """Handle payment failed event to release inventory."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")

            if order_id:
                # Auto-release any reservations for this order
                result = await self.inventory_service.release_inventory(order_id)

                if result.get("success", False):
                    await self.publish_business_event(
                        event_type="inventory_auto_released",
                        event_data={"order_id": order_id, "reason": "Payment failed"},
                        aggregate_id=order_id,
                    )

        except Exception as e:
            logger.error(f"Error handling payment failed event: {e}")


if __name__ == "__main__":
    consumer = InventoryConsumer()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(consumer.start_consuming())
    except KeyboardInterrupt:
        print("Inventory Consumer shutting down...")
    finally:
        loop.run_until_complete(consumer.close())

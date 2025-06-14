import asyncio
from typing import Dict, Any

from common.base_consumer import BaseServiceConsumer
from common.centralized_logging import get_logger
from .service import PaymentService
from .models import PaymentRequest, RefundRequest

logger = get_logger(__name__)


class PaymentConsumer(BaseServiceConsumer):
    def __init__(self):
        self.payment_service = PaymentService()
        super().__init__("payment", self.payment_service)
        self.setup_service_handlers()

    async def setup_service_handlers(self):
        """Setup payment service specific command and event handlers."""
        # Register payment-specific saga commands
        self.register_command_handler("process_payment", self._handle_process_payment)
        self.register_command_handler("refund_payment", self._handle_refund_payment)
        self.register_command_handler("verify_payment", self._handle_verify_payment)
        self.register_command_handler(
            "get_payment_status", self._handle_get_payment_status
        )

        # Register event handlers for data consistency
        self.register_event_handler("order_created", self._handle_order_created)
        self.register_event_handler("order_cancelled", self._handle_order_cancelled)
        self.register_event_handler(
            "inventory_reservation_failed", self._handle_inventory_reservation_failed
        )
        self.register_event_handler("shipping_failed", self._handle_shipping_failed)

    # Saga command handlers
    async def _handle_process_payment(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle process payment saga command."""
        try:
            # Extract payment data
            order_id = payload.get("order_id")
            amount = payload.get("amount")
            currency = payload.get("currency", "USD")
            payment_method = payload.get("payment_method")
            customer_id = payload.get("customer_id")

            if not all([order_id, amount, payment_method, customer_id]):
                raise ValueError(
                    "order_id, amount, payment_method, and customer_id are required"
                )

            # Create payment request
            payment_request = PaymentRequest(
                order_id=order_id,
                amount=float(amount),
                currency=currency,
                payment_method=payment_method,
                customer_id=customer_id,
                description=payload.get("description", f"Payment for order {order_id}"),
            )

            # Process payment
            result = await self.payment_service.process_payment(payment_request)

            # Publish domain event for payment processing
            if result.get("success", False):
                await self.publish_business_event(
                    event_type="payment_completed",
                    event_data={
                        "order_id": order_id,
                        "payment_id": result.get("payment_id"),
                        "amount": amount,
                        "currency": currency,
                        "payment_method": payment_method,
                        "transaction_id": result.get("transaction_id"),
                    },
                    aggregate_id=order_id,
                )
            else:
                await self.publish_business_event(
                    event_type="payment_failed",
                    event_data={
                        "order_id": order_id,
                        "amount": amount,
                        "currency": currency,
                        "payment_method": payment_method,
                        "reason": result.get("message", "Unknown error"),
                    },
                    aggregate_id=order_id,
                )

            return result

        except Exception as e:
            # Publish domain event for payment failure
            await self.publish_business_event(
                event_type="payment_failed",
                event_data={
                    "order_id": payload.get("order_id"),
                    "error": str(e),
                    "amount": payload.get("amount"),
                },
            )
            raise

    async def _handle_refund_payment(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle refund payment saga command (compensation)."""
        try:
            payment_id = payload.get("payment_id")
            order_id = payload.get("order_id")
            amount = payload.get("amount")
            reason = payload.get("reason", "Saga compensation")

            if not payment_id and not order_id:
                raise ValueError(
                    "Either payment_id or order_id is required for refund_payment command"
                )

            # Create refund request
            refund_request = RefundRequest(
                payment_id=payment_id,
                order_id=order_id,
                amount=float(amount) if amount else None,
                reason=reason,
            )

            # Process refund
            result = await self.payment_service.refund_payment(refund_request)

            # Publish domain event for refund processing
            if result.get("success", False):
                await self.publish_business_event(
                    event_type="payment_refunded",
                    event_data={
                        "order_id": order_id,
                        "payment_id": payment_id,
                        "refund_id": result.get("refund_id"),
                        "amount": result.get("refund_amount"),
                        "reason": reason,
                        "saga_id": message.get("saga_id"),
                    },
                    aggregate_id=order_id or payment_id,
                )
            else:
                await self.publish_business_event(
                    event_type="payment_refund_failed",
                    event_data={
                        "order_id": order_id,
                        "payment_id": payment_id,
                        "reason": result.get("message", "Unknown error"),
                    },
                    aggregate_id=order_id or payment_id,
                )

            return result

        except Exception as e:
            await self.publish_business_event(
                event_type="payment_refund_failed",
                event_data={
                    "order_id": payload.get("order_id"),
                    "payment_id": payload.get("payment_id"),
                    "error": str(e),
                },
            )
            raise

    async def _handle_verify_payment(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle verify payment command."""
        try:
            payment_id = payload.get("payment_id")
            order_id = payload.get("order_id")

            if not payment_id and not order_id:
                raise ValueError("Either payment_id or order_id is required")

            result = await self.payment_service.verify_payment(payment_id, order_id)

            # Publish domain event for payment verification
            await self.publish_business_event(
                event_type="payment_verified",
                event_data={
                    "order_id": order_id,
                    "payment_id": payment_id,
                    "verification_result": result,
                },
                aggregate_id=order_id or payment_id,
            )

            return result

        except Exception as e:
            await self.publish_business_event(
                event_type="payment_verification_failed",
                event_data={
                    "order_id": payload.get("order_id"),
                    "payment_id": payload.get("payment_id"),
                    "error": str(e),
                },
            )
            raise

    async def _handle_get_payment_status(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle get payment status command."""
        order_id = payload.get("order_id")
        payment_id = payload.get("payment_id")

        if not order_id and not payment_id:
            raise ValueError("Either order_id or payment_id is required")

        result = await self.payment_service.get_payment_status(order_id, payment_id)
        return result

    # Event handlers for data consistency
    async def _handle_order_created(self, event: Dict[str, Any]):
        """Handle order created event to prepare for payment processing."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")
            total_amount = event_data.get("total_amount")
            customer_id = event_data.get("customer_id")

            if all([order_id, total_amount, customer_id]):
                # Validate payment readiness
                await self.publish_business_event(
                    event_type="payment_readiness_checked",
                    event_data={
                        "order_id": order_id,
                        "total_amount": total_amount,
                        "customer_id": customer_id,
                        "ready_for_payment": True,
                    },
                    aggregate_id=order_id,
                )

        except Exception as e:
            logger.error(f"Error handling order created event: {e}")

    async def _handle_order_cancelled(self, event: Dict[str, Any]):
        """Handle order cancelled event to process refunds if needed."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")

            if order_id:
                # Check if there are any payments to refund
                payment_status = await self.payment_service.get_payment_status(
                    order_id=order_id
                )

                if payment_status.get("has_successful_payments", False):
                    # Auto-initiate refund for cancelled orders
                    refund_request = RefundRequest(
                        order_id=order_id, reason="Order cancelled"
                    )

                    result = await self.payment_service.refund_payment(refund_request)

                    if result.get("success", False):
                        await self.publish_business_event(
                            event_type="payment_auto_refunded",
                            event_data={
                                "order_id": order_id,
                                "refund_id": result.get("refund_id"),
                                "reason": "Order cancelled",
                            },
                            aggregate_id=order_id,
                        )

        except Exception as e:
            logger.error(f"Error handling order cancelled event: {e}")

    async def _handle_inventory_reservation_failed(self, event: Dict[str, Any]):
        """Handle inventory reservation failed event to process refunds."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")

            if order_id:
                # Check if payment was already processed
                payment_status = await self.payment_service.get_payment_status(
                    order_id=order_id
                )

                if payment_status.get("has_successful_payments", False):
                    # Auto-initiate refund for inventory failure
                    refund_request = RefundRequest(
                        order_id=order_id, reason="Inventory reservation failed"
                    )

                    result = await self.payment_service.refund_payment(refund_request)

                    if result.get("success", False):
                        await self.publish_business_event(
                            event_type="payment_auto_refunded",
                            event_data={
                                "order_id": order_id,
                                "refund_id": result.get("refund_id"),
                                "reason": "Inventory reservation failed",
                            },
                            aggregate_id=order_id,
                        )

        except Exception as e:
            logger.error(f"Error handling inventory reservation failed event: {e}")

    async def _handle_shipping_failed(self, event: Dict[str, Any]):
        """Handle shipping failed event to process refunds if needed."""
        try:
            event_data = event.get("event_data", {})
            order_id = event_data.get("order_id")

            if order_id:
                # Check if payment was processed
                payment_status = await self.payment_service.get_payment_status(
                    order_id=order_id
                )

                if payment_status.get("has_successful_payments", False):
                    # Auto-initiate refund for shipping failure
                    refund_request = RefundRequest(
                        order_id=order_id, reason="Shipping failed"
                    )

                    result = await self.payment_service.refund_payment(refund_request)

                    if result.get("success", False):
                        await self.publish_business_event(
                            event_type="payment_auto_refunded",
                            event_data={
                                "order_id": order_id,
                                "refund_id": result.get("refund_id"),
                                "reason": "Shipping failed",
                            },
                            aggregate_id=order_id,
                        )

        except Exception as e:
            logger.error(f"Error handling shipping failed event: {e}")


if __name__ == "__main__":
    consumer = PaymentConsumer()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(consumer.start_consuming())
    except KeyboardInterrupt:
        print("Payment Consumer shutting down...")
    finally:
        loop.run_until_complete(consumer.close())

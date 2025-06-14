import uuid
from typing import Dict, Any, List
import sys
from pathlib import Path

# Add parent directory to path to import common modules
sys.path.append(str(Path(__file__).resolve().parents[1]))

from common.saga import Saga, SagaStep, SagaStatus


class OrderSaga(Saga):
    """Order Saga Orchestrator"""

    def __init__(self, order_data: Dict[str, Any]):
        saga_id = str(uuid.uuid4())
        super().__init__(
            saga_id, f"Order Saga for order {order_data.get('order_id', 'new')}"
        )

        # Store the initial order data in the context
        self.context.update({"order_data": order_data})

        # Define the saga steps
        self._define_steps()

    def _define_steps(self):
        """Define the steps of the order saga with command mappings for Kafka."""

        # Step 1: Create Order
        self.add_step(
            SagaStep(
                service="order",
                action_command="create_order",
                compensation_command="cancel_order",
                request_data=self.context.get("order_data", {}),
            )
        )

        # Step 2: Reserve Inventory
        self.add_step(
            SagaStep(
                service="inventory",
                action_command="reserve_inventory",
                compensation_command="release_inventory",
                request_data={},  # Will be populated from order creation response
            )
        )

        # Step 3: Process Payment
        self.add_step(
            SagaStep(
                service="payment",
                action_command="process_payment",
                compensation_command="refund_payment",
                request_data={},  # Will be populated from order creation response
            )
        )

        # Step 4: Schedule Shipping
        self.add_step(
            SagaStep(
                service="shipping",
                action_command="schedule_shipping",
                compensation_command="cancel_shipping",
                request_data={},  # Will be populated from order creation response
            )
        )

        # Step 5: Send Notification
        self.add_step(
            SagaStep(
                service="notification",
                action_command="send_notification",
                compensation_command="cancel_notification",
                request_data={
                    "notification_type": "order_confirmation",
                    "channel": "email",
                },
            )
        )

    async def process_order(self) -> Dict[str, Any]:
        """Process the order by executing the saga with proper error handling"""
        try:
            print(f"Starting saga {self.id} for order processing")

            # Execute the saga
            result = await self.execute()

            # Extract order_id from context if available
            order_id = self.context.get("order_id")

            # Return comprehensive result
            return {
                "saga_id": self.id,
                "order_id": order_id,
                "status": (
                    self.status.value
                    if hasattr(self.status, "value")
                    else str(self.status)
                ),
                "message": self._get_status_message(),
                "details": result,
                "steps_completed": len([s for s in self.steps if s.is_executed]),
                "total_steps": len(self.steps),
            }

        except Exception as e:
            print(f"Critical error in saga {self.id}: {str(e)}")
            self.status = SagaStatus.FAILED

            return {
                "saga_id": self.id,
                "order_id": self.context.get("order_id"),
                "status": self.status.value,
                "message": f"Saga failed: {str(e)}",
                "details": {"error": str(e)},
                "steps_completed": len([s for s in self.steps if s.is_executed]),
                "total_steps": len(self.steps),
            }

    def _get_status_message(self) -> str:
        """Get human-readable status message"""
        if self.status == SagaStatus.COMPLETED:
            return "Order processing completed successfully"
        elif self.status == SagaStatus.FAILED:
            return "Order processing failed and compensated"
        elif self.status == SagaStatus.ABORTED:
            return "Order processing was aborted and compensated"
        elif self.status == SagaStatus.STARTED:
            return "Order processing in progress"
        else:
            return f"Order processing status: {self.status}"

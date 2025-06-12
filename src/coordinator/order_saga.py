import uuid
from typing import Dict, Any, List
import sys
import os

# Add parent directory to path to import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        """Define the steps of the order saga"""

        # Step 1: Create Order
        self.add_step(
            SagaStep(
                service="order",
                action_endpoint="api/orders/create",
                compensation_endpoint="api/orders/cancel",
                request_data=self.context.get("order_data", {}),
            )
        )

        # Step 2: Reserve Inventory
        self.add_step(
            SagaStep(
                service="inventory",
                action_endpoint="api/inventory/reserve",
                compensation_endpoint="api/inventory/release",
                request_data={},  # Will be populated from order creation response
            )
        )

        # Step 3: Process Payment
        self.add_step(
            SagaStep(
                service="payment",
                action_endpoint="api/payments/process",
                compensation_endpoint="api/payments/refund",
                request_data={},  # Will be populated from order creation response
            )
        )

        # Step 4: Schedule Shipping
        self.add_step(
            SagaStep(
                service="shipping",
                action_endpoint="api/shipping/schedule",
                compensation_endpoint="api/shipping/cancel",
                request_data={},  # Will be populated from order creation response
            )
        )

        # Optional Step 5: Send Notification (no compensation needed)
        self.add_step(
            SagaStep(
                service="notification",
                action_endpoint="api/notifications/send",
                compensation_endpoint="api/notifications/cancel",
                request_data={"notification_type": "order_confirmation"},
            )
        )

    async def process_order(self) -> Dict[str, Any]:
        """Process the order by executing the saga"""
        result = await self.execute()

        # Return a simplified result for API response
        return {
            "saga_id": self.id,
            "order_id": self.context.get("order_id"),
            "status": self.status,
            "message": f"Order processing {self.status.lower()}",
            "details": result,
        }

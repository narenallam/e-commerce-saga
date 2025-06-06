from enum import Enum
from typing import List, Dict, Any, Callable, Optional
from .messaging import ServiceCommunicator


class SagaStatus(str, Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class SagaStep:
    def __init__(
        self,
        service: str,
        action_endpoint: str,
        compensation_endpoint: str,
        request_data: Optional[Dict[str, Any]] = None,
    ):
        self.service = service
        self.action_endpoint = action_endpoint
        self.compensation_endpoint = compensation_endpoint
        self.request_data = request_data or {}
        self.is_executed = False
        self.response_data = None

    async def execute(
        self, communicator: ServiceCommunicator, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the step's action"""
        merged_data = {**self.request_data, **context}
        self.response_data = await communicator.send_request(
            self.service, self.action_endpoint, method="POST", data=merged_data
        )
        self.is_executed = True
        return self.response_data

    async def compensate(
        self, communicator: ServiceCommunicator, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the step's compensation action"""
        if not self.is_executed:
            return None

        merged_data = {**self.request_data, **context}
        if self.response_data:
            merged_data["original_response"] = self.response_data

        return await communicator.send_request(
            self.service, self.compensation_endpoint, method="POST", data=merged_data
        )


class Saga:
    def __init__(self, saga_id: str, description: str = ""):
        self.id = saga_id
        self.description = description
        self.steps: List[SagaStep] = []
        self.status = SagaStatus.STARTED
        self.context: Dict[str, Any] = {"saga_id": saga_id}
        self.communicator = ServiceCommunicator()
        self.failed_step_index = -1

    def add_step(self, step: SagaStep) -> "Saga":
        """Add a step to the saga"""
        self.steps.append(step)
        return self

    async def execute(self) -> Dict[str, Any]:
        """Execute all steps in order, compensate on failure"""
        try:
            # Execute each step
            for i, step in enumerate(self.steps):
                step_result = await step.execute(self.communicator, self.context)

                # Update context with the result from this step
                if step_result:
                    self.context.update(step_result)

            self.status = SagaStatus.COMPLETED
            return {"status": self.status, "context": self.context}

        except Exception as e:
            self.status = SagaStatus.FAILED
            self.failed_step_index = i
            print(f"Saga {self.id} failed at step {i}: {str(e)}")

            # Trigger compensation
            await self.compensate()

            return {
                "status": self.status,
                "error": str(e),
                "failed_step": i,
                "context": self.context,
            }

    async def compensate(self) -> None:
        """Compensate executed steps in reverse order"""
        self.status = SagaStatus.ABORTED

        # Compensate steps in reverse order up to the failed step
        for i in range(self.failed_step_index, -1, -1):
            step = self.steps[i]
            try:
                await step.compensate(self.communicator, self.context)
            except Exception as e:
                print(f"Compensation failed for step {i}: {str(e)}")
                # Continue with other compensations even if one fails

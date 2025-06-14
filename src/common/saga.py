from enum import Enum
from typing import List, Dict, Any, Callable, Optional
from .kafka import KafkaClient
from .centralized_logging import get_logger

logger = get_logger(__name__)


class SagaStatus(str, Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class SagaStep:
    def __init__(
        self,
        service: str,
        action_command: str,
        compensation_command: str,
        request_data: Optional[Dict[str, Any]] = None,
    ):
        self.service = service
        self.action_command = action_command
        self.compensation_command = compensation_command
        self.request_data = request_data or {}
        self.is_executed = False
        self.response_data = None

    async def execute(
        self, kafka_client: KafkaClient, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the step's action via Kafka with enhanced event-driven approach."""
        topic = f"{self.service}_commands"

        # Create saga command with enhanced metadata
        saga_command = {
            "command": self.action_command,
            "payload": {**self.request_data, **context},
            "saga_id": context.get("saga_id"),
            "step_service": self.service,
            "step_action": self.action_command,
        }

        try:
            self.response_data = await kafka_client.send_saga_command(
                topic, saga_command
            )
            self.is_executed = True

            # Publish domain event for successful step execution
            await kafka_client.publish_domain_event(
                event_type="saga_step_completed",
                aggregate_id=context.get("saga_id"),
                event_data={
                    "service": self.service,
                    "action": self.action_command,
                    "response": self.response_data,
                },
            )

            logger.info(
                f"Saga step executed successfully: {self.service}:{self.action_command}"
            )
            return self.response_data

        except Exception as e:
            # Publish domain event for failed step execution
            await kafka_client.publish_domain_event(
                event_type="saga_step_failed",
                aggregate_id=context.get("saga_id"),
                event_data={
                    "service": self.service,
                    "action": self.action_command,
                    "error": str(e),
                },
            )
            logger.error(
                f"Saga step failed: {self.service}:{self.action_command} - {str(e)}"
            )
            raise

    async def compensate(
        self, kafka_client: KafkaClient, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the step's compensation action via Kafka with enhanced event-driven approach."""
        if not self.is_executed:
            return None

        topic = f"{self.service}_commands"
        merged_data = {**self.request_data, **context}
        if self.response_data:
            merged_data["original_response"] = self.response_data

        # Create compensation command with enhanced metadata
        compensation_command = {
            "command": self.compensation_command,
            "payload": merged_data,
            "saga_id": context.get("saga_id"),
            "step_service": self.service,
            "step_action": self.compensation_command,
            "is_compensation": True,
        }

        try:
            result = await kafka_client.send_saga_command(topic, compensation_command)

            # Publish domain event for successful compensation
            await kafka_client.publish_domain_event(
                event_type="saga_step_compensated",
                aggregate_id=context.get("saga_id"),
                event_data={
                    "service": self.service,
                    "compensation_action": self.compensation_command,
                    "result": result,
                },
            )

            logger.info(
                f"Saga step compensated successfully: {self.service}:{self.compensation_command}"
            )
            return result

        except Exception as e:
            # Publish domain event for failed compensation
            await kafka_client.publish_domain_event(
                event_type="saga_compensation_failed",
                aggregate_id=context.get("saga_id"),
                event_data={
                    "service": self.service,
                    "compensation_action": self.compensation_command,
                    "error": str(e),
                },
            )
            logger.error(
                f"Saga compensation failed: {self.service}:{self.compensation_command} - {str(e)}"
            )
            raise


class Saga:
    def __init__(self, saga_id: str, description: str = ""):
        self.id = saga_id
        self.description = description
        self.steps: List[SagaStep] = []
        self.status = SagaStatus.STARTED
        self.context: Dict[str, Any] = {"saga_id": saga_id}
        self.kafka_client = KafkaClient(
            group_id=f"saga-coordinator-{saga_id}", service_name="saga-coordinator"
        )
        self.failed_step_index = -1

    def add_step(self, step: SagaStep) -> "Saga":
        """Add a step to the saga"""
        self.steps.append(step)
        return self

    async def execute(self) -> Dict[str, Any]:
        """Execute all steps in order with robust error handling using Kafka and event-driven patterns."""
        await self.kafka_client.connect()
        execution_log = []

        try:
            logger.info(f"Executing saga {self.id} with {len(self.steps)} steps")

            # Publish saga started event
            await self.kafka_client.publish_domain_event(
                event_type="saga_started",
                aggregate_id=self.id,
                event_data={
                    "description": self.description,
                    "steps_count": len(self.steps),
                    "context": self.context,
                },
            )

            for i, step in enumerate(self.steps):
                step_name = f"{step.service}:{step.action_command}"
                logger.info(f"Executing step {i+1}/{len(self.steps)}: {step_name}")

                try:
                    step_context = self._prepare_step_context(step, i)
                    step_result = await step.execute(self.kafka_client, step_context)

                    execution_log.append(
                        {
                            "step": i,
                            "service": step.service,
                            "action": step.action_command,
                            "status": "SUCCESS",
                            "result": step_result,
                        }
                    )
                    self._update_context_from_step_result(step_result, step.service)
                    logger.info(f"Step {i+1} completed successfully")

                except Exception as step_error:
                    logger.error(f"Step {i+1} failed: {str(step_error)}")
                    self.failed_step_index = i
                    execution_log.append(
                        {
                            "step": i,
                            "service": step.service,
                            "action": step.action_command,
                            "status": "FAILED",
                            "error": str(step_error),
                        }
                    )
                    raise step_error

            self.status = SagaStatus.COMPLETED
            logger.info(f"Saga {self.id} completed successfully")

            # Publish saga completed event
            await self.kafka_client.publish_domain_event(
                event_type="saga_completed",
                aggregate_id=self.id,
                event_data={
                    "execution_log": execution_log,
                    "final_context": self.context,
                },
            )

            return {
                "status": self.status.value,
                "message": "All saga steps completed successfully",
                "context": self.context,
                "execution_log": execution_log,
            }

        except Exception as e:
            self.status = SagaStatus.FAILED
            logger.error(
                f"Saga {self.id} failed at step {self.failed_step_index + 1}: {str(e)}"
            )

            # Publish saga failed event
            await self.kafka_client.publish_domain_event(
                event_type="saga_failed",
                aggregate_id=self.id,
                event_data={
                    "failed_step": self.failed_step_index,
                    "error": str(e),
                    "execution_log": execution_log,
                },
            )

            compensation_result = await self.compensate()
            return {
                "status": self.status.value,
                "error": str(e),
                "failed_step": self.failed_step_index,
                "message": f"Saga failed at step {self.failed_step_index + 1} and compensated",
                "context": self.context,
                "execution_log": execution_log,
                "compensation_result": compensation_result,
            }
        finally:
            await self.kafka_client.close()

    def _prepare_step_context(self, step: SagaStep, step_index: int) -> Dict[str, Any]:
        """Prepare context data for a specific step with enhanced metadata"""
        step_context = {**self.context}

        # Add step-specific data
        if step.request_data:
            step_context.update(step.request_data)

        # Add step metadata for better traceability
        step_context.update(
            {
                "step_index": step_index,
                "saga_id": self.id,
                "step_service": step.service,
                "total_steps": len(self.steps),
                "saga_description": self.description,
            }
        )

        return step_context

    def _update_context_from_step_result(
        self, step_result: Dict[str, Any], service: str
    ):
        """Update saga context with results from a step for better data consistency"""
        if not step_result:
            return

        # Service-specific context updates with enhanced data extraction
        if service == "order" and "order_id" in step_result:
            self.context["order_id"] = step_result["order_id"]
            if "total_amount" in step_result:
                self.context["order_total"] = step_result["total_amount"]
        elif service == "inventory" and "reservations" in step_result:
            self.context["inventory_reservations"] = step_result["reservations"]
            if "reserved_items" in step_result:
                self.context["reserved_items"] = step_result["reserved_items"]
        elif service == "payment" and "payment_id" in step_result:
            self.context["payment_id"] = step_result["payment_id"]
            if "payment_status" in step_result:
                self.context["payment_status"] = step_result["payment_status"]
        elif service == "shipping" and "tracking_number" in step_result:
            self.context["tracking_number"] = step_result["tracking_number"]
            if "shipping_id" in step_result:
                self.context["shipping_id"] = step_result["shipping_id"]
        elif service == "notification" and "notification_id" in step_result:
            self.context["notification_id"] = step_result["notification_id"]

        # Always store the full step result for compensation and debugging
        self.context[f"{service}_step_result"] = step_result

        # Add timestamp for better tracking
        import asyncio

        self.context[f"{service}_completed_at"] = asyncio.get_event_loop().time()

    async def compensate(self) -> Dict[str, Any]:
        """Compensate executed steps in reverse order using Kafka with enhanced event-driven patterns."""
        self.status = SagaStatus.ABORTED
        compensation_log = []

        logger.info(f"Starting compensation for saga {self.id}")

        # Publish saga compensation started event
        await self.kafka_client.publish_domain_event(
            event_type="saga_compensation_started",
            aggregate_id=self.id,
            event_data={
                "failed_step": self.failed_step_index,
                "steps_to_compensate": self.failed_step_index + 1,
            },
        )

        if self.failed_step_index < 0:
            logger.info("No steps to compensate")
            return {"compensation_log": [], "message": "No steps to compensate"}

        for i in range(self.failed_step_index, -1, -1):
            step = self.steps[i]
            if not step.is_executed:
                logger.info(f"Skipping compensation for step {i} (not executed)")
                continue

            step_name = f"{step.service}:{step.compensation_command}"
            logger.info(f"Compensating step {i+1}: {step_name}")

            try:
                compensation_context = self._prepare_compensation_context(step, i)
                compensation_result = await step.compensate(
                    self.kafka_client, compensation_context
                )
                compensation_log.append(
                    {
                        "step": i,
                        "service": step.service,
                        "compensation_action": step.compensation_command,
                        "status": "SUCCESS",
                        "result": compensation_result,
                    }
                )
                logger.info(f"Compensation for step {i+1} completed successfully")

            except Exception as e:
                logger.error(f"Compensation failed for step {i+1}: {str(e)}")
                compensation_log.append(
                    {
                        "step": i,
                        "service": step.service,
                        "compensation_action": step.compensation_command,
                        "status": "FAILED",
                        "error": str(e),
                    }
                )

        logger.info(f"Compensation completed for saga {self.id}")

        # Publish saga compensation completed event
        await self.kafka_client.publish_domain_event(
            event_type="saga_compensation_completed",
            aggregate_id=self.id,
            event_data={
                "compensation_log": compensation_log,
                "compensated_steps": len(
                    [log for log in compensation_log if log["status"] == "SUCCESS"]
                ),
                "failed_compensations": len(
                    [log for log in compensation_log if log["status"] == "FAILED"]
                ),
            },
        )

        return {
            "compensation_log": compensation_log,
            "message": f"Compensated {len(compensation_log)} steps",
            "compensated_steps": len(
                [log for log in compensation_log if log["status"] == "SUCCESS"]
            ),
            "failed_compensations": len(
                [log for log in compensation_log if log["status"] == "FAILED"]
            ),
        }

    def _prepare_compensation_context(
        self, step: SagaStep, step_index: int
    ) -> Dict[str, Any]:
        """Prepare context data for compensation with enhanced metadata"""
        compensation_context = {**self.context}

        # Add original step data
        if step.request_data:
            compensation_context.update(step.request_data)

        # Add the original response from this step for compensation
        if step.response_data:
            compensation_context["original_response"] = step.response_data

        # Add compensation metadata with enhanced traceability
        compensation_context.update(
            {
                "step_index": step_index,
                "saga_id": self.id,
                "compensation_service": step.service,
                "is_compensation": True,
                "failed_step_index": self.failed_step_index,
                "saga_status": self.status.value,
            }
        )

        return compensation_context

    async def get_event_history(self) -> List[Dict[str, Any]]:
        """Get the event history for this saga for debugging and auditing purposes."""
        return await self.kafka_client.get_event_store()

    async def replay_from_checkpoint(self, checkpoint_step: int = 0) -> Dict[str, Any]:
        """Replay saga from a specific checkpoint for recovery purposes."""
        logger.info(f"Replaying saga {self.id} from step {checkpoint_step}")

        # Reset saga state
        self.status = SagaStatus.STARTED
        self.failed_step_index = -1

        # Mark previous steps as not executed
        for i in range(checkpoint_step):
            if i < len(self.steps):
                self.steps[i].is_executed = False

        # Execute from checkpoint
        return await self.execute()

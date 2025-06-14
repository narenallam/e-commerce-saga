import asyncio
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from .kafka import KafkaClient
from .centralized_logging import get_logger

logger = get_logger(__name__)


class BaseServiceConsumer(ABC):
    """
    Base consumer class for all microservices in the e-commerce saga system.
    Provides common event-driven patterns and saga integration.
    """

    def __init__(self, service_name: str, service_instance=None):
        self.service_name = service_name
        self.service_instance = service_instance
        self.kafka_client = KafkaClient(
            group_id=f"{service_name}-service-group", service_name=service_name
        )
        self.command_handlers = {}
        self.event_handlers = {}
        self._setup_default_handlers()

    def _setup_default_handlers(self):
        """Setup default command and event handlers."""
        # Default saga commands - to be overridden by subclasses
        self.command_handlers = {
            "health_check": self._handle_health_check,
            "get_statistics": self._handle_get_statistics,
        }

        # Default event handlers for domain events
        self.event_handlers = {
            "saga_started": self._handle_saga_started,
            "saga_completed": self._handle_saga_completed,
            "saga_failed": self._handle_saga_failed,
        }

    async def initialize(self):
        """Initialize the consumer, kafka client, and service instance."""
        await self.kafka_client.connect()
        if self.service_instance and hasattr(self.service_instance, "initialize"):
            await self.service_instance.initialize()
        await self._register_handlers()
        logger.info(f"{self.service_name} consumer initialized successfully")

    async def _register_handlers(self):
        """Register command and event handlers with Kafka client."""
        for command, handler in self.command_handlers.items():
            await self.kafka_client.register_command_handler(command, handler)
        logger.info(
            f"Registered {len(self.command_handlers)} command handlers for {self.service_name}"
        )

    async def handle_saga_command(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming saga commands from Kafka with enhanced error handling.
        This ensures data consistency across services in the saga pattern.
        """
        command = message.get("command")
        payload = message.get("payload", {})
        correlation_id = message.get("correlation_id")
        saga_id = message.get("saga_id")
        reply_topic = message.get("reply_topic")

        # Validate required fields
        if not all([command, reply_topic, correlation_id]):
            logger.error(f"Missing required fields in saga command: {message}")
            return await self._send_error_reply(
                reply_topic, correlation_id, "Missing required fields in command"
            )

        # Get command handler
        handler = self.command_handlers.get(command)
        if not handler:
            logger.error(f"Unknown command: {command} for service {self.service_name}")
            return await self._send_error_reply(
                reply_topic, correlation_id, f"Unknown command: {command}"
            )

        try:
            # Execute command handler
            logger.info(f"Processing saga command '{command}' for saga {saga_id}")
            result = await handler(payload, message)

            # Send successful reply
            reply_message = {
                "correlation_id": correlation_id,
                "saga_id": saga_id,
                "service": self.service_name,
                "command": command,
                "status": "success",
                "payload": result.dict() if hasattr(result, "dict") else result,
                "timestamp": asyncio.get_event_loop().time(),
            }

            await self.kafka_client.publish_message(reply_topic, reply_message)
            logger.info(
                f"Successfully processed saga command '{command}' for saga {saga_id}"
            )

            # Publish domain event for successful command processing
            await self.kafka_client.publish_domain_event(
                event_type="command_processed",
                aggregate_id=saga_id or correlation_id,
                event_data={
                    "command": command,
                    "service": self.service_name,
                    "result": result.dict() if hasattr(result, "dict") else result,
                },
            )

            return reply_message

        except Exception as e:
            logger.error(
                f"Error processing saga command '{command}' for saga {saga_id}: {e}"
            )
            return await self._send_error_reply(
                reply_topic, correlation_id, str(e), saga_id
            )

    async def _send_error_reply(
        self,
        reply_topic: str,
        correlation_id: str,
        error_message: str,
        saga_id: str = None,
    ):
        """Send error reply for failed command processing."""
        error_reply = {
            "correlation_id": correlation_id,
            "saga_id": saga_id,
            "service": self.service_name,
            "status": "error",
            "error": error_message,
            "timestamp": asyncio.get_event_loop().time(),
        }

        await self.kafka_client.publish_message(reply_topic, error_reply)

        # Publish domain event for failed command processing
        if saga_id:
            await self.kafka_client.publish_domain_event(
                event_type="command_failed",
                aggregate_id=saga_id,
                event_data={
                    "service": self.service_name,
                    "error": error_message,
                    "correlation_id": correlation_id,
                },
            )

        return error_reply

    async def handle_domain_event(self, event: Dict[str, Any]):
        """Handle domain events from other services for eventual consistency."""
        event_type = event.get("event_type")
        aggregate_id = event.get("aggregate_id")

        if not event_type:
            logger.warning(f"Received domain event without event_type: {event}")
            return

        logger.info(
            f"Processing domain event '{event_type}' for aggregate {aggregate_id}"
        )

        # Get event handler
        handler = self.event_handlers.get(event_type)
        if handler:
            try:
                await handler(event)
                logger.info(f"Successfully processed domain event '{event_type}'")
            except Exception as e:
                logger.error(f"Error processing domain event '{event_type}': {e}")
        else:
            logger.debug(
                f"No handler for domain event '{event_type}' in service {self.service_name}"
            )

    async def start_consuming(self):
        """Start consuming messages from Kafka topics."""
        await self.initialize()

        # Start consuming saga commands
        command_topic = f"{self.service_name}_commands"
        logger.info(f"Starting to consume from '{command_topic}' topic")

        # Start consuming domain events for eventual consistency
        domain_events_topic = f"{self.service_name}_domain_events"

        # Start both consumers concurrently
        await asyncio.gather(
            self.kafka_client.consume_commands(command_topic, self.handle_saga_command),
            self.kafka_client.consume_commands(
                domain_events_topic, self.handle_domain_event
            ),
            return_exceptions=True,
        )

    async def close(self):
        """Close the Kafka client connection."""
        await self.kafka_client.close()
        logger.info(f"{self.service_name} consumer closed successfully")

    # Default command handlers
    async def _handle_health_check(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Default health check handler."""
        return {
            "status": "healthy",
            "service": self.service_name,
            "timestamp": asyncio.get_event_loop().time(),
        }

    async def _handle_get_statistics(
        self, payload: Dict[str, Any], message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Default statistics handler."""
        if self.service_instance and hasattr(self.service_instance, "get_statistics"):
            return await self.service_instance.get_statistics()
        return {
            "service": self.service_name,
            "message": "Statistics not available",
            "timestamp": asyncio.get_event_loop().time(),
        }

    # Default event handlers
    async def _handle_saga_started(self, event: Dict[str, Any]):
        """Handle saga started events for logging and monitoring."""
        saga_id = event.get("aggregate_id")
        event_data = event.get("event_data", {})
        logger.info(f"Saga {saga_id} started - {self.service_name} service notified")

    async def _handle_saga_completed(self, event: Dict[str, Any]):
        """Handle saga completed events for cleanup and logging."""
        saga_id = event.get("aggregate_id")
        event_data = event.get("event_data", {})
        logger.info(f"Saga {saga_id} completed - {self.service_name} service notified")

    async def _handle_saga_failed(self, event: Dict[str, Any]):
        """Handle saga failed events for alerting and cleanup."""
        saga_id = event.get("aggregate_id")
        event_data = event.get("event_data", {})
        logger.warning(f"Saga {saga_id} failed - {self.service_name} service notified")

    # Abstract methods to be implemented by subclasses
    @abstractmethod
    async def setup_service_handlers(self):
        """Setup service-specific command and event handlers."""
        pass

    def register_command_handler(self, command: str, handler: Callable):
        """Register a command handler."""
        self.command_handlers[command] = handler
        logger.info(
            f"Registered command handler for '{command}' in {self.service_name}"
        )

    def register_event_handler(self, event_type: str, handler: Callable):
        """Register an event handler."""
        self.event_handlers[event_type] = handler
        logger.info(
            f"Registered event handler for '{event_type}' in {self.service_name}"
        )

    async def publish_business_event(
        self, event_type: str, event_data: Dict[str, Any], aggregate_id: str = None
    ):
        """Publish business events for other services to consume."""
        await self.kafka_client.publish_domain_event(
            event_type=event_type,
            aggregate_id=aggregate_id
            or f"{self.service_name}_{asyncio.get_event_loop().time()}",
            event_data=event_data,
        )

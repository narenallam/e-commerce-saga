import os
import json
import asyncio
import uuid
from typing import Callable, Dict, Any, List, Optional
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.helpers import create_ssl_context
from .config import get_kafka_config
from .centralized_logging import get_logger

logger = get_logger(__name__)


class KafkaClient:
    def __init__(self, group_id: str, service_name: str = "unknown"):
        self.producer = None
        self.consumer = None
        self.rpc_futures = {}
        self.group_id = group_id
        self.service_name = service_name

        # Get configuration
        self.kafka_config = get_kafka_config()
        self.kafka_bootstrap_servers = self.kafka_config["bootstrap_servers"]
        self.reply_topic = f"saga_reply_{group_id}_{uuid.uuid4()}"

        # Event store for saga consistency
        self.event_store: List[Dict[str, Any]] = []
        self.message_handlers: Dict[str, Callable] = {}

    async def connect(self):
        """Establish connection to Kafka with production-ready configuration."""
        try:
            # Enhanced producer configuration for reliability
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                enable_idempotence=self.kafka_config.get("enable_idempotence", True),
                acks=self.kafka_config.get("acks", "all"),
                retries=self.kafka_config.get("retries", 3),
                batch_size=self.kafka_config.get("batch_size", 16384),
                linger_ms=self.kafka_config.get("linger_ms", 10),
                buffer_memory=self.kafka_config.get("buffer_memory", 33554432),
                compression_type="gzip",
                value_serializer=lambda x: json.dumps(x).encode("utf-8"),
            )
            await self.producer.start()
            logger.info(f"Kafka producer connected for service {self.service_name}")

            # Enhanced consumer configuration for reliability
            self.consumer = AIOKafkaConsumer(
                self.reply_topic,
                bootstrap_servers=self.kafka_bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.kafka_config.get(
                    "auto_offset_reset", "earliest"
                ),
                enable_auto_commit=self.kafka_config.get("enable_auto_commit", True),
                auto_commit_interval_ms=self.kafka_config.get(
                    "auto_commit_interval_ms", 5000
                ),
                session_timeout_ms=self.kafka_config.get("session_timeout_ms", 30000),
                heartbeat_interval_ms=self.kafka_config.get(
                    "heartbeat_interval_ms", 3000
                ),
                max_poll_records=self.kafka_config.get("max_poll_records", 500),
                max_poll_interval_ms=self.kafka_config.get(
                    "max_poll_interval_ms", 300000
                ),
                value_deserializer=lambda x: json.loads(x.decode("utf-8")),
            )
            await self.consumer.start()
            logger.info(f"Kafka consumer connected for service {self.service_name}")

            # Start reply listener
            asyncio.create_task(self._listen_for_replies())
            logger.info(
                f"Successfully connected to Kafka for service {self.service_name}"
            )

        except Exception as e:
            logger.error(
                f"Failed to connect to Kafka for service {self.service_name}: {e}"
            )
            raise

    async def close(self):
        """Close Kafka connections gracefully."""
        try:
            if self.producer:
                await self.producer.stop()
                logger.info(f"Kafka producer closed for service {self.service_name}")
            if self.consumer:
                await self.consumer.stop()
                logger.info(f"Kafka consumer closed for service {self.service_name}")
        except Exception as e:
            logger.error(
                f"Error closing Kafka connections for service {self.service_name}: {e}"
            )

    async def publish_event(
        self, topic: str, event: Dict[str, Any], partition_key: Optional[str] = None
    ):
        """
        Publish an event to Kafka topic with enhanced reliability.
        This is for event-driven architecture pattern.
        """
        if not self.producer:
            raise ConnectionError("Not connected to Kafka.")

        try:
            # Add event metadata for traceability
            enhanced_event = {
                **event,
                "event_id": str(uuid.uuid4()),
                "service_name": self.service_name,
                "timestamp": asyncio.get_event_loop().time(),
                "event_type": "business_event",
            }

            # Store event locally for consistency
            self.event_store.append(enhanced_event)

            # Publish to Kafka with optional partitioning
            key = partition_key.encode("utf-8") if partition_key else None
            await self.producer.send_and_wait(topic, enhanced_event, key=key)

            logger.info(
                f"Published event to topic '{topic}' from service {self.service_name}"
            )

        except Exception as e:
            logger.error(f"Failed to publish event to topic '{topic}': {e}")
            raise

    async def publish_message(self, topic: str, message: Dict[str, Any]):
        """Publish a message to a Kafka topic (backward compatibility)."""
        await self.publish_event(topic, message)

    async def send_saga_command(
        self, topic: str, command: Dict[str, Any], timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Send a saga command and wait for a reply with enhanced error handling.
        This ensures data consistency across services in saga pattern.
        """
        correlation_id = str(uuid.uuid4())
        saga_command = {
            **command,
            "reply_topic": self.reply_topic,
            "correlation_id": correlation_id,
            "saga_id": command.get("saga_id", str(uuid.uuid4())),
            "command_type": "saga_command",
            "source_service": self.service_name,
            "timestamp": asyncio.get_event_loop().time(),
        }

        future = asyncio.get_event_loop().create_future()
        self.rpc_futures[correlation_id] = future

        try:
            await self.publish_event(topic, saga_command)
            logger.info(
                f"Sent saga command to topic '{topic}' with correlation_id {correlation_id}"
            )

            return await asyncio.wait_for(future, timeout)

        except asyncio.TimeoutError:
            del self.rpc_futures[correlation_id]
            logger.error(
                f"Saga command timed out for topic '{topic}' with correlation_id {correlation_id}"
            )
            raise TimeoutError(f"Saga command timed out for topic '{topic}'")
        except Exception as e:
            if correlation_id in self.rpc_futures:
                del self.rpc_futures[correlation_id]
            logger.error(f"Error sending saga command to topic '{topic}': {e}")
            raise

    async def send_request(
        self, topic: str, message: Dict[str, Any], timeout: int = 30
    ) -> Dict[str, Any]:
        """Send a request and wait for a reply (backward compatibility)."""
        return await self.send_saga_command(topic, message, timeout)

    async def _listen_for_replies(self):
        """Listen for reply messages on the dedicated reply topic."""
        try:
            logger.info(f"Starting reply listener for service {self.service_name}")
            async for msg in self.consumer:
                try:
                    reply = msg.value
                    correlation_id = reply.get("correlation_id")

                    if correlation_id in self.rpc_futures:
                        self.rpc_futures[correlation_id].set_result(reply)
                        del self.rpc_futures[correlation_id]
                        logger.debug(
                            f"Processed reply for correlation_id {correlation_id}"
                        )
                    else:
                        logger.warning(
                            f"Received reply for unknown correlation_id {correlation_id}"
                        )

                except Exception as e:
                    logger.error(f"Error processing reply message: {e}")
        except Exception as e:
            logger.error(f"Reply listener stopped with error: {e}")
        finally:
            logger.info(f"Reply listener stopped for service {self.service_name}")

    async def register_command_handler(self, command: str, handler: Callable):
        """Register a command handler for event-driven processing."""
        self.message_handlers[command] = handler
        logger.info(
            f"Registered command handler for '{command}' in service {self.service_name}"
        )

    async def consume_commands(self, topic: str, callback: Optional[Callable] = None):
        """
        Consume commands from a specific topic with enhanced error handling.
        Supports both saga commands and business events for complete event-driven architecture.
        """
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self.kafka_bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset=self.kafka_config.get("auto_offset_reset", "earliest"),
            enable_auto_commit=self.kafka_config.get("enable_auto_commit", True),
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        )

        await consumer.start()
        logger.info(
            f"Started consuming from topic '{topic}' for service {self.service_name}"
        )

        try:
            async for msg in consumer:
                try:
                    message_data = msg.value

                    # Handle both saga commands and business events
                    command_type = message_data.get("command_type", "business_event")

                    if callback:
                        await callback(message_data)
                    else:
                        await self._handle_message(message_data)

                    logger.debug(f"Processed {command_type} from topic '{topic}'")

                except Exception as e:
                    logger.error(f"Error processing message from topic '{topic}': {e}")
                    # Implement dead letter queue logic here if needed

        except Exception as e:
            logger.error(f"Consumer error for topic '{topic}': {e}")
        finally:
            await consumer.stop()
            logger.info(
                f"Stopped consuming from topic '{topic}' for service {self.service_name}"
            )

    async def consume_topic(self, topic: str, callback: Callable):
        """Consume messages from a specific topic (backward compatibility)."""
        await self.consume_commands(topic, callback)

    async def _handle_message(self, message_data: Dict[str, Any]):
        """Handle incoming messages using registered handlers."""
        command = message_data.get("command")
        if command and command in self.message_handlers:
            handler = self.message_handlers[command]
            await handler(message_data)
        else:
            logger.warning(
                f"No handler registered for command '{command}' in service {self.service_name}"
            )

    async def publish_domain_event(
        self, event_type: str, aggregate_id: str, event_data: Dict[str, Any]
    ):
        """
        Publish domain events for event sourcing and CQRS patterns.
        This ensures data consistency across service boundaries.
        """
        topic = f"{self.service_name}_domain_events"

        domain_event = {
            "event_type": event_type,
            "aggregate_id": aggregate_id,
            "aggregate_type": self.service_name,
            "event_data": event_data,
            "event_version": 1,
            "occurred_at": asyncio.get_event_loop().time(),
        }

        await self.publish_event(topic, domain_event, partition_key=aggregate_id)
        logger.info(
            f"Published domain event '{event_type}' for aggregate {aggregate_id}"
        )

    async def get_event_store(self) -> List[Dict[str, Any]]:
        """Get stored events for debugging and replay purposes."""
        return self.event_store.copy()

    async def replay_events(self, from_timestamp: float = 0) -> List[Dict[str, Any]]:
        """Replay events from a specific timestamp for recovery purposes."""
        replayed_events = [
            event
            for event in self.event_store
            if event.get("timestamp", 0) >= from_timestamp
        ]
        logger.info(
            f"Replaying {len(replayed_events)} events from timestamp {from_timestamp}"
        )
        return replayed_events

import pytest
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from src.common.kafka import KafkaClient
from src.common.saga import Saga, SagaStep
from src.common.base_consumer import BaseServiceConsumer


class TestKafkaIntegration:
    """Test suite for Kafka integration and event-driven architecture."""

    @pytest.fixture
    async def kafka_client(self):
        """Create a mock Kafka client for testing."""
        with patch("src.common.kafka.AIOKafkaProducer"), patch(
            "src.common.kafka.AIOKafkaConsumer"
        ):
            client = KafkaClient(group_id="test-group", service_name="test-service")
            # Mock the connect method to avoid actual Kafka connection
            client.connect = AsyncMock()
            client.close = AsyncMock()
            client.producer = AsyncMock()
            client.consumer = AsyncMock()
            yield client

    @pytest.mark.asyncio
    async def test_kafka_client_initialization(self, kafka_client):
        """Test that Kafka client initializes correctly with enhanced configuration."""
        assert kafka_client.service_name == "test-service"
        assert kafka_client.group_id == "test-group"
        assert "test-group" in kafka_client.reply_topic
        assert isinstance(kafka_client.event_store, list)
        assert isinstance(kafka_client.message_handlers, dict)

    @pytest.mark.asyncio
    async def test_publish_event(self, kafka_client):
        """Test event publishing with metadata enrichment."""
        # Setup
        await kafka_client.connect()

        # Test data
        topic = "test_topic"
        event = {"test_key": "test_value"}

        # Execute
        await kafka_client.publish_event(topic, event)

        # Verify
        kafka_client.producer.send_and_wait.assert_called_once()
        call_args = kafka_client.producer.send_and_wait.call_args

        # Check that event was enriched with metadata
        published_event = call_args[0][1]  # Second argument is the event
        assert published_event["test_key"] == "test_value"
        assert "event_id" in published_event
        assert published_event["service_name"] == "test-service"
        assert published_event["event_type"] == "business_event"
        assert "timestamp" in published_event

        # Check that event was stored locally
        assert len(kafka_client.event_store) == 1
        assert kafka_client.event_store[0] == published_event

    @pytest.mark.asyncio
    async def test_send_saga_command(self, kafka_client):
        """Test saga command sending with enhanced metadata."""
        # Setup
        await kafka_client.connect()
        kafka_client.rpc_futures = {}

        # Mock future for reply
        future = asyncio.Future()
        future.set_result({"status": "success", "result": "test_result"})

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.create_future.return_value = future
            mock_loop.return_value.time.return_value = 1234567890.0

            # Test data
            topic = "test_commands"
            command = {"command": "test_command", "payload": {"test": "data"}}

            # Execute
            result = await kafka_client.send_saga_command(topic, command)

            # Verify
            assert result["status"] == "success"
            kafka_client.producer.send_and_wait.assert_called_once()

            # Check saga command structure
            call_args = kafka_client.producer.send_and_wait.call_args
            published_command = call_args[0][1]
            assert published_command["command"] == "test_command"
            assert published_command["command_type"] == "saga_command"
            assert published_command["source_service"] == "test-service"
            assert "correlation_id" in published_command
            assert "saga_id" in published_command

    @pytest.mark.asyncio
    async def test_publish_domain_event(self, kafka_client):
        """Test domain event publishing for event sourcing."""
        # Setup
        await kafka_client.connect()

        # Test data
        event_type = "order_created"
        aggregate_id = "order-123"
        event_data = {"customer_id": "cust-456", "amount": 100.0}

        # Execute
        await kafka_client.publish_domain_event(event_type, aggregate_id, event_data)

        # Verify
        kafka_client.producer.send_and_wait.assert_called_once()
        call_args = kafka_client.producer.send_and_wait.call_args

        # Check domain event structure
        domain_event = call_args[0][1]
        assert domain_event["event_type"] == event_type
        assert domain_event["aggregate_id"] == aggregate_id
        assert domain_event["aggregate_type"] == "test-service"
        assert domain_event["event_data"] == event_data
        assert domain_event["event_version"] == 1
        assert "occurred_at" in domain_event

    @pytest.mark.asyncio
    async def test_saga_enhanced_execution(self):
        """Test enhanced saga execution with event-driven patterns."""
        # Create mock Kafka client
        with patch("src.common.saga.KafkaClient") as MockKafkaClient:
            mock_kafka = AsyncMock()
            MockKafkaClient.return_value = mock_kafka

            # Setup saga
            saga_id = str(uuid.uuid4())
            saga = Saga(saga_id, "Test Order Saga")

            # Add test step
            step = SagaStep(
                service="order",
                action_command="create_order",
                compensation_command="cancel_order",
                request_data={"customer_id": "test-customer"},
            )
            saga.add_step(step)

            # Mock step response
            mock_kafka.send_saga_command.return_value = {
                "order_id": "order-123",
                "status": "created",
            }

            # Execute saga
            result = await saga.execute()

            # Verify saga execution
            assert result["status"] == "COMPLETED"
            assert "execution_log" in result
            assert len(result["execution_log"]) == 1

            # Verify domain events were published
            mock_kafka.publish_domain_event.assert_called()

            # Check that saga events were published
            domain_event_calls = mock_kafka.publish_domain_event.call_args_list
            event_types = [call[1]["event_type"] for call in domain_event_calls]
            assert "saga_started" in event_types
            assert "saga_step_completed" in event_types
            assert "saga_completed" in event_types

    @pytest.mark.asyncio
    async def test_saga_compensation_with_events(self):
        """Test saga compensation with event publishing."""
        with patch("src.common.saga.KafkaClient") as MockKafkaClient:
            mock_kafka = AsyncMock()
            MockKafkaClient.return_value = mock_kafka

            # Setup saga
            saga_id = str(uuid.uuid4())
            saga = Saga(saga_id, "Test Failed Saga")

            # Add test steps
            step1 = SagaStep("order", "create_order", "cancel_order")
            step2 = SagaStep("payment", "process_payment", "refund_payment")
            saga.add_step(step1).add_step(step2)

            # Mock first step success, second step failure
            mock_kafka.send_saga_command.side_effect = [
                {"order_id": "order-123", "status": "created"},
                Exception("Payment failed"),
            ]

            # Execute saga (should fail and compensate)
            result = await saga.execute()

            # Verify saga failed and compensated
            assert result["status"] == "FAILED"
            assert "compensation_result" in result

            # Verify compensation events were published
            domain_event_calls = mock_kafka.publish_domain_event.call_args_list
            event_types = [call[1]["event_type"] for call in domain_event_calls]
            assert "saga_failed" in event_types
            assert "saga_compensation_started" in event_types
            assert "saga_step_compensated" in event_types
            assert "saga_compensation_completed" in event_types


class TestBaseServiceConsumer:
    """Test suite for BaseServiceConsumer functionality."""

    class TestConsumer(BaseServiceConsumer):
        """Test consumer implementation."""

        def __init__(self):
            super().__init__("test-service")

        async def setup_service_handlers(self):
            self.register_command_handler("test_command", self._handle_test_command)
            self.register_event_handler("test_event", self._handle_test_event)

        async def _handle_test_command(self, payload, message):
            return {"result": "command_handled", "payload": payload}

        async def _handle_test_event(self, event):
            # Just log the event handling
            pass

    @pytest.fixture
    async def test_consumer(self):
        """Create a test consumer."""
        with patch("src.common.base_consumer.KafkaClient"):
            consumer = self.TestConsumer()
            consumer.kafka_client = AsyncMock()
            return consumer

    @pytest.mark.asyncio
    async def test_consumer_initialization(self, test_consumer):
        """Test consumer initialization and handler registration."""
        assert test_consumer.service_name == "test-service"
        assert "test_command" in test_consumer.command_handlers
        assert "test_event" in test_consumer.event_handlers
        assert "health_check" in test_consumer.command_handlers
        assert "get_statistics" in test_consumer.command_handlers

    @pytest.mark.asyncio
    async def test_handle_saga_command(self, test_consumer):
        """Test saga command handling with proper reply generation."""
        # Test message
        message = {
            "command": "test_command",
            "payload": {"test_data": "value"},
            "correlation_id": "corr-123",
            "saga_id": "saga-456",
            "reply_topic": "test_reply_topic",
        }

        # Execute
        result = await test_consumer.handle_saga_command(message)

        # Verify
        assert result["correlation_id"] == "corr-123"
        assert result["saga_id"] == "saga-456"
        assert result["service"] == "test-service"
        assert result["status"] == "success"
        assert result["payload"]["result"] == "command_handled"

        # Verify reply was published
        test_consumer.kafka_client.publish_message.assert_called_once()

        # Verify domain event was published
        test_consumer.kafka_client.publish_domain_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_unknown_command(self, test_consumer):
        """Test handling of unknown commands."""
        # Test message with unknown command
        message = {
            "command": "unknown_command",
            "payload": {},
            "correlation_id": "corr-123",
            "reply_topic": "test_reply_topic",
        }

        # Execute
        result = await test_consumer.handle_saga_command(message)

        # Verify error response
        assert result["status"] == "error"
        assert "Unknown command" in result["error"]
        assert result["correlation_id"] == "corr-123"

    @pytest.mark.asyncio
    async def test_handle_domain_event(self, test_consumer):
        """Test domain event handling."""
        # Test event
        event = {
            "event_type": "test_event",
            "aggregate_id": "test-123",
            "event_data": {"test": "data"},
        }

        # Mock event handler
        test_consumer._handle_test_event = AsyncMock()

        # Execute
        await test_consumer.handle_domain_event(event)

        # Verify handler was called
        test_consumer._handle_test_event.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_publish_business_event(self, test_consumer):
        """Test business event publishing."""
        # Execute
        await test_consumer.publish_business_event(
            event_type="test_business_event",
            event_data={"business": "data"},
            aggregate_id="business-123",
        )

        # Verify domain event was published
        test_consumer.kafka_client.publish_domain_event.assert_called_once_with(
            event_type="test_business_event",
            aggregate_id="business-123",
            event_data={"business": "data"},
        )

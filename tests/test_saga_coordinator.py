import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# Add src to path for imports
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from coordinator.order_saga import OrderSaga
from common.saga import Saga, SagaStep, SagaStatus
from common.messaging import ServiceCommunicator


@pytest.fixture
def sample_order_data():
    """Create sample order data for testing"""
    return {
        "customer_id": "test-customer-123",
        "items": [
            {
                "product_id": "prod-1",
                "name": "Test Product 1",
                "quantity": 2,
                "unit_price": 99.99,
                "total_price": 199.98,
            },
            {
                "product_id": "prod-2",
                "name": "Test Product 2",
                "quantity": 1,
                "unit_price": 49.99,
                "total_price": 49.99,
            },
        ],
        "total_amount": 249.97,
        "customer_details": {
            "email": "test@example.com",
            "address": "123 Test St",
            "city": "Test City",
            "country": "Test Country",
        },
    }


@pytest.fixture
def mock_service_communicator():
    """Create a mock service communicator"""
    communicator = AsyncMock(spec=ServiceCommunicator)

    # Mock successful service responses
    communicator.send_request.return_value = {
        "success": True,
        "order_id": "test-order-123",
        "status": "success",
    }

    communicator.health_check.return_value = True
    communicator.check_all_services_health.return_value = {
        "order": True,
        "inventory": True,
        "payment": True,
        "shipping": True,
        "notification": True,
    }

    return communicator


@pytest.fixture
def order_saga_with_mock(sample_order_data, mock_service_communicator):
    """Create an OrderSaga with mocked communicator"""
    saga = OrderSaga(sample_order_data)
    saga.communicator = mock_service_communicator
    return saga


@pytest.mark.asyncio
async def test_order_saga_initialization(sample_order_data):
    """Test OrderSaga initialization"""
    saga = OrderSaga(sample_order_data)

    # Check basic properties
    assert saga.id is not None
    assert len(saga.steps) == 5  # Order, Inventory, Payment, Shipping, Notification
    assert saga.status == SagaStatus.STARTED
    assert saga.context["order_data"] == sample_order_data

    # Check step definitions
    steps = saga.steps
    assert steps[0].service == "order"
    assert steps[0].action_endpoint == "api/orders"
    assert steps[1].service == "inventory"
    assert steps[1].action_endpoint == "api/inventory/reserve"
    assert steps[2].service == "payment"
    assert steps[2].action_endpoint == "api/payments/process"
    assert steps[3].service == "shipping"
    assert steps[3].action_endpoint == "api/shipping/schedule"
    assert steps[4].service == "notification"
    assert steps[4].action_endpoint == "api/notifications/send"


@pytest.mark.asyncio
async def test_successful_saga_execution(
    order_saga_with_mock, mock_service_communicator
):
    """Test successful saga execution through all steps"""
    # Mock different responses for each service
    mock_responses = [
        {"order_id": "test-order-123", "status": "created"},
        {"success": True, "reservations": [{"reservation_id": "res-1"}]},
        {"payment_id": "pay-123", "status": "completed"},
        {"tracking_number": "track-456", "status": "scheduled"},
        {"notification_id": "notif-789", "status": "sent"},
    ]

    mock_service_communicator.send_request.side_effect = mock_responses

    # Execute the saga
    result = await order_saga_with_mock.process_order()

    # Assertions
    assert result["status"] == "COMPLETED"
    assert result["order_id"] == "test-order-123"
    assert "successfully" in result["message"].lower()
    assert result["steps_completed"] == 5
    assert result["total_steps"] == 5

    # Check that all steps were executed
    assert all(step.is_executed for step in order_saga_with_mock.steps)

    # Check context updates
    assert order_saga_with_mock.context["order_id"] == "test-order-123"
    assert "inventory_reservations" in order_saga_with_mock.context
    assert order_saga_with_mock.context["payment_id"] == "pay-123"
    assert order_saga_with_mock.context["tracking_number"] == "track-456"


@pytest.mark.asyncio
async def test_saga_failure_and_compensation(
    order_saga_with_mock, mock_service_communicator
):
    """Test saga failure at inventory step and compensation"""
    # Mock responses: Order succeeds, Inventory fails
    mock_responses = [
        {"order_id": "test-order-123", "status": "created"},  # Order succeeds
        Exception("Insufficient inventory"),  # Inventory fails
    ]

    mock_service_communicator.send_request.side_effect = mock_responses

    # Mock compensation responses
    compensation_responses = [
        {"success": True, "cancelled": True}  # Order cancellation
    ]

    # Execute the saga
    result = await order_saga_with_mock.process_order()

    # Assertions
    assert result["status"] == "FAILED"
    assert result["order_id"] == "test-order-123"
    assert "failed" in result["message"].lower()
    assert result["steps_completed"] == 1  # Only order step completed
    assert result["total_steps"] == 5
    assert result["failed_step"] == 1  # Inventory step (0-indexed)

    # Check saga status
    assert order_saga_with_mock.status == SagaStatus.ABORTED
    assert order_saga_with_mock.failed_step_index == 1


@pytest.mark.asyncio
async def test_saga_step_context_preparation():
    """Test step context preparation"""
    saga = Saga("test-saga", "Test saga")
    saga.context = {
        "saga_id": "test-saga",
        "order_id": "test-order-123",
        "customer_id": "test-customer",
    }

    step = SagaStep(
        service="inventory",
        action_endpoint="api/inventory/reserve",
        compensation_endpoint="api/inventory/release",
        request_data={"special_param": "value"},
    )

    # Test context preparation
    step_context = saga._prepare_step_context(step, 1)

    # Assertions
    assert step_context["saga_id"] == "test-saga"
    assert step_context["order_id"] == "test-order-123"
    assert step_context["special_param"] == "value"  # From request_data
    assert step_context["step_index"] == 1
    assert step_context["step_service"] == "inventory"


@pytest.mark.asyncio
async def test_saga_context_updates():
    """Test context updates from step results"""
    saga = Saga("test-saga", "Test saga")

    # Test order service result
    saga._update_context_from_step_result(
        {"order_id": "test-order-123", "status": "created"}, "order"
    )
    assert saga.context["order_id"] == "test-order-123"
    assert saga.context["order_step_result"]["status"] == "created"

    # Test inventory service result
    saga._update_context_from_step_result(
        {"reservations": [{"id": "res-1"}], "success": True}, "inventory"
    )
    assert saga.context["inventory_reservations"] == [{"id": "res-1"}]
    assert saga.context["inventory_step_result"]["success"] is True

    # Test payment service result
    saga._update_context_from_step_result(
        {"payment_id": "pay-123", "status": "completed"}, "payment"
    )
    assert saga.context["payment_id"] == "pay-123"


@pytest.mark.asyncio
async def test_compensation_context_preparation():
    """Test compensation context preparation"""
    saga = Saga("test-saga", "Test saga")
    saga.context = {"saga_id": "test-saga", "order_id": "test-order"}

    step = SagaStep(
        service="inventory",
        action_endpoint="api/inventory/reserve",
        compensation_endpoint="api/inventory/release",
        request_data={"quantity": 5},
    )
    step.response_data = {"reservation_id": "res-123", "success": True}

    # Test compensation context preparation
    comp_context = saga._prepare_compensation_context(step, 1)

    # Assertions
    assert comp_context["saga_id"] == "test-saga"
    assert comp_context["order_id"] == "test-order"
    assert comp_context["quantity"] == 5  # From original request
    assert comp_context["original_response"]["reservation_id"] == "res-123"
    assert comp_context["step_index"] == 1
    assert comp_context["compensation_service"] == "inventory"
    assert comp_context["is_compensation"] is True


@pytest.mark.asyncio
async def test_saga_step_execution():
    """Test individual saga step execution"""
    # Create a mock communicator
    mock_communicator = AsyncMock()
    mock_communicator.send_request.return_value = {
        "order_id": "test-order-123",
        "status": "created",
    }

    # Create a step
    step = SagaStep(
        service="order",
        action_endpoint="api/orders",
        compensation_endpoint="api/orders/cancel",
        request_data={"customer_id": "test-customer"},
    )

    # Execute the step
    context = {"saga_id": "test-saga"}
    result = await step.execute(mock_communicator, context)

    # Assertions
    assert step.is_executed is True
    assert step.response_data == result
    assert result["order_id"] == "test-order-123"

    # Verify the request was made correctly
    mock_communicator.send_request.assert_called_once_with(
        "order", "api/orders", method="POST", data={**step.request_data, **context}
    )


@pytest.mark.asyncio
async def test_saga_step_compensation():
    """Test individual saga step compensation"""
    # Create a mock communicator
    mock_communicator = AsyncMock()
    mock_communicator.send_request.return_value = {"success": True, "cancelled": True}

    # Create a step that was previously executed
    step = SagaStep(
        service="order",
        action_endpoint="api/orders",
        compensation_endpoint="api/orders/cancel",
        request_data={"customer_id": "test-customer"},
    )
    step.is_executed = True
    step.response_data = {"order_id": "test-order-123"}

    # Execute compensation
    context = {"saga_id": "test-saga"}
    result = await step.compensate(mock_communicator, context)

    # Assertions
    assert result["success"] is True

    # Verify the compensation request was made correctly
    expected_data = {
        **step.request_data,
        **context,
        "original_response": step.response_data,
    }
    mock_communicator.send_request.assert_called_once_with(
        "order", "api/orders/cancel", method="POST", data=expected_data
    )


@pytest.mark.asyncio
async def test_service_communicator_health_check():
    """Test service communicator health check functionality"""
    communicator = ServiceCommunicator()

    # Mock successful health check
    with patch.object(
        communicator, "send_request", new_callable=AsyncMock
    ) as mock_send:
        mock_send.return_value = {"status": "healthy"}

        # Test individual service health check
        is_healthy = await communicator.health_check("order")
        assert is_healthy is True

        mock_send.assert_called_with("order", "health", method="GET", timeout=5.0)

    # Mock failed health check
    with patch.object(
        communicator, "send_request", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = Exception("Service unavailable")

        is_healthy = await communicator.health_check("inventory")
        assert is_healthy is False


@pytest.mark.asyncio
async def test_service_communicator_all_services_health():
    """Test checking health of all services"""
    communicator = ServiceCommunicator()

    # Mock mixed health results
    health_responses = {
        "order": {"status": "healthy"},
        "inventory": {"status": "healthy"},
        "payment": Exception("Service down"),
        "shipping": {"status": "healthy"},
        "notification": Exception("Service down"),
    }

    async def mock_health_check(service):
        response = health_responses[service]
        if isinstance(response, Exception):
            return False
        return True

    with patch.object(communicator, "health_check", side_effect=mock_health_check):
        health_results = await communicator.check_all_services_health()

        expected = {
            "order": True,
            "inventory": True,
            "payment": False,
            "shipping": True,
            "notification": False,
        }

        assert health_results == expected


@pytest.mark.asyncio
async def test_order_saga_status_messages(sample_order_data):
    """Test status message generation"""
    saga = OrderSaga(sample_order_data)

    # Test different status messages
    saga.status = SagaStatus.COMPLETED
    assert "completed successfully" in saga._get_status_message().lower()

    saga.status = SagaStatus.FAILED
    assert "failed and compensated" in saga._get_status_message().lower()

    saga.status = SagaStatus.ABORTED
    assert "aborted and compensated" in saga._get_status_message().lower()

    saga.status = SagaStatus.STARTED
    assert "in progress" in saga._get_status_message().lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

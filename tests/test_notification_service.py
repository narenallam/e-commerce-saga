import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Add src to path for imports
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from services.notification.service import NotificationService
from services.notification.models import (
    NotificationStatus,
    NotificationType,
    NotificationChannel,
)


@pytest.fixture
def mock_notification_service():
    """Create a mock notification service for testing"""
    service = NotificationService()
    service.db = AsyncMock()
    service.notifications_collection = "notifications"
    service.templates_collection = "notification_templates"
    return service


@pytest.fixture
def sample_notification_data():
    """Create sample notification data for testing"""
    return {
        "notification_type": "order_confirmation",
        "customer_id": "test-customer-123",
        "order_id": "test-order-123",
        "channels": ["email"],
        "data": {
            "customer_name": "John Doe",
            "order_id": "test-order-123",
            "total_amount": 199.99,
        },
        "order_data": {
            "order_id": "test-order-123",
            "customer_id": "test-customer-123",
        },
    }


@pytest.mark.asyncio
async def test_send_notification_success(
    mock_notification_service, sample_notification_data
):
    """Test successful notification sending"""
    # Mock successful notification sending
    mock_notification_service._simulate_notification_sending = MagicMock(
        return_value=True
    )

    # Mock database insertion
    mock_notification_service.db[
        mock_notification_service.notifications_collection
    ].insert_one = AsyncMock()

    # Send notification
    result = await mock_notification_service.send_notification(sample_notification_data)

    # Assertions
    assert result["status"] == NotificationStatus.SENT.value
    assert result["notification_type"] == "order_confirmation"
    assert result["customer_id"] == "test-customer-123"
    assert result["order_id"] == "test-order-123"
    assert "sent_at" in result


@pytest.mark.asyncio
async def test_send_notification_failure(
    mock_notification_service, sample_notification_data
):
    """Test notification sending failure"""
    # Mock notification sending failure
    mock_notification_service._simulate_notification_sending = MagicMock(
        return_value=False
    )

    # Mock database insertion
    mock_notification_service.db[
        mock_notification_service.notifications_collection
    ].insert_one = AsyncMock()

    # Send notification - should not raise exception (notifications don't fail sagas)
    result = await mock_notification_service.send_notification(sample_notification_data)

    # Assertions
    assert result["status"] == NotificationStatus.FAILED.value
    assert "error_message" in result
    assert result["error_message"] == "Failed to send notification"


@pytest.mark.asyncio
async def test_get_notification_success(mock_notification_service):
    """Test successful notification retrieval"""
    notification_id = "test-notification-123"

    # Mock database response
    mock_notification_data = {
        "notification_id": notification_id,
        "notification_type": "order_confirmation",
        "customer_id": "test-customer-123",
        "order_id": "test-order-123",
        "channels": ["email"],
        "status": "SENT",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "sent_at": datetime.now(),
    }

    mock_notification_service.db[
        mock_notification_service.notifications_collection
    ].find_one.return_value = mock_notification_data

    # Get notification
    notification = await mock_notification_service.get_notification(notification_id)

    # Assertions
    assert notification is not None
    assert notification["notification_id"] == notification_id
    assert notification["status"] == "SENT"
    assert notification["notification_type"] == "order_confirmation"


@pytest.mark.asyncio
async def test_get_notification_not_found(mock_notification_service):
    """Test notification retrieval when notification doesn't exist"""
    notification_id = "non-existent-notification"

    # Mock database response (no notification found)
    mock_notification_service.db[
        mock_notification_service.notifications_collection
    ].find_one.return_value = None

    # Get notification
    notification = await mock_notification_service.get_notification(notification_id)

    # Assertions
    assert notification is None


@pytest.mark.asyncio
async def test_cancel_notification_success(mock_notification_service):
    """Test successful notification cancellation"""
    notification_id = "test-notification-123"
    order_id = "test-order-123"

    # Mock database update result
    mock_update_result = MagicMock()
    mock_update_result.modified_count = 2  # Cancelled 2 pending notifications
    mock_notification_service.db[
        mock_notification_service.notifications_collection
    ].update_many.return_value = mock_update_result

    # Cancel notification
    cancel_data = {
        "notification_id": notification_id,
        "order_id": order_id,
        "reason": "Order cancelled",
    }

    result = await mock_notification_service.cancel_notification(cancel_data)

    # Assertions
    assert result["success"] is True
    assert result["modified_count"] == 2
    assert "Cancelled 2 notification(s)" in result["message"]


@pytest.mark.asyncio
async def test_cancel_notification_none_found(mock_notification_service):
    """Test cancellation when no notifications found to cancel"""
    notification_id = "test-notification-123"
    order_id = "test-order-123"

    # Mock database update result (no notifications modified)
    mock_update_result = MagicMock()
    mock_update_result.modified_count = 0
    mock_notification_service.db[
        mock_notification_service.notifications_collection
    ].update_many.return_value = mock_update_result

    # Cancel notification
    cancel_data = {
        "notification_id": notification_id,
        "order_id": order_id,
    }

    result = await mock_notification_service.cancel_notification(cancel_data)

    # Assertions
    assert result["success"] is True
    assert result["modified_count"] == 0
    assert "No notifications found to cancel" in result["message"]


@pytest.mark.asyncio
async def test_cancel_notification_missing_ids(mock_notification_service):
    """Test cancellation when no IDs provided"""
    # Cancel notification without notification_id or order_id
    cancel_data = {"reason": "Test cancellation"}

    result = await mock_notification_service.cancel_notification(cancel_data)

    # Assertions
    assert result["success"] is False
    assert "notification_id or order_id is required" in result["message"]


@pytest.mark.asyncio
async def test_list_notifications(mock_notification_service):
    """Test listing notifications with filtering"""
    # Mock database response
    mock_notifications = [
        {
            "notification_id": "notification-1",
            "customer_id": "customer-123",
            "order_id": "order-123",
            "notification_type": "order_confirmation",
            "status": "SENT",
            "channels": ["email"],
        },
        {
            "notification_id": "notification-2",
            "customer_id": "customer-123",
            "order_id": "order-456",
            "notification_type": "payment_confirmation",
            "status": "PENDING",
            "channels": ["email", "sms"],
        },
    ]

    # Mock cursor
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = mock_notifications

    mock_notification_service.db[
        mock_notification_service.notifications_collection
    ].find.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor

    # List notifications
    notifications = await mock_notification_service.list_notifications(
        customer_id="customer-123",
        status=NotificationStatus.SENT,
        notification_type=NotificationType.ORDER_CONFIRMATION,
        limit=10,
        skip=0,
    )

    # Assertions
    assert len(notifications) == 2
    assert notifications[0]["notification_id"] == "notification-1"
    assert notifications[1]["notification_id"] == "notification-2"


@pytest.mark.asyncio
async def test_send_notification_with_defaults(mock_notification_service):
    """Test notification sending with default values"""
    # Mock successful notification sending
    mock_notification_service._simulate_notification_sending = MagicMock(
        return_value=True
    )

    # Mock database insertion
    mock_notification_service.db[
        mock_notification_service.notifications_collection
    ].insert_one = AsyncMock()

    # Send notification with minimal data
    minimal_data = {
        "order_data": {
            "order_id": "test-order-123",
            "customer_id": "test-customer-123",
        }
    }

    result = await mock_notification_service.send_notification(minimal_data)

    # Assertions
    assert result["status"] == NotificationStatus.SENT.value
    assert result["notification_type"] == NotificationType.ORDER_CONFIRMATION.value
    assert result["customer_id"] == "test-customer-123"
    assert result["order_id"] == "test-order-123"
    assert result["channels"] == [NotificationChannel.EMAIL.value]
    assert result["template_id"] == "order_confirmation_email"


@pytest.mark.asyncio
async def test_create_sample_templates(mock_notification_service):
    """Test sample template creation"""
    # Mock database operations
    mock_notification_service.db[
        mock_notification_service.templates_collection
    ].count_documents.return_value = 0
    mock_notification_service.db[
        mock_notification_service.templates_collection
    ].insert_many = AsyncMock()

    # Initialize service (should create templates)
    await mock_notification_service.initialize()

    # Verify templates were created
    mock_notification_service.db[
        mock_notification_service.templates_collection
    ].insert_many.assert_called_once()

    # Get the templates that were inserted
    call_args = mock_notification_service.db[
        mock_notification_service.templates_collection
    ].insert_many.call_args
    templates = call_args[0][0]  # First argument of the call

    # Assertions
    assert len(templates) == 4  # Should create 4 templates
    template_types = [t["notification_type"] for t in templates]
    assert "order_confirmation" in template_types
    assert "payment_confirmation" in template_types
    assert "shipping_confirmation" in template_types
    assert "order_cancelled" in template_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

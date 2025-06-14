import pytest
import asyncio
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock

# Add src to path for imports
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from services.shipping.service import ShippingService
from services.shipping.models import ShippingStatus, ShippingMethod


@pytest.fixture
def mock_shipping_service():
    """Create a mock shipping service for testing"""
    service = ShippingService()
    service.db = AsyncMock()
    service.shipments_collection = "shipments"
    return service


@pytest.fixture
def sample_shipping_data():
    """Create sample shipping data for testing"""
    return {
        "order_id": "test-order-123",
        "customer_id": "test-customer-123",
        "address": {
            "street": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
            "country": "US",
        },
        "items": [{"product_id": "prod-1", "name": "Test Product", "quantity": 2}],
        "method": "STANDARD",
        "order_data": {
            "order_id": "test-order-123",
            "customer_id": "test-customer-123",
            "shipping_address": {
                "street": "123 Test St",
                "city": "Test City",
                "state": "TS",
                "zip_code": "12345",
                "country": "US",
            },
            "items": [{"product_id": "prod-1", "name": "Test Product", "quantity": 2}],
        },
    }


@pytest.mark.asyncio
async def test_schedule_shipping_success(mock_shipping_service, sample_shipping_data):
    """Test successful shipping scheduling"""
    # Mock successful shipping scheduling
    mock_shipping_service._simulate_shipping_scheduling = MagicMock(return_value=True)

    # Mock database insertion
    mock_shipping_service.db[mock_shipping_service.shipments_collection].insert_one = (
        AsyncMock()
    )

    # Schedule shipping
    result = await mock_shipping_service.schedule_shipping(sample_shipping_data)

    # Assertions
    assert result["status"] == ShippingStatus.SCHEDULED.value
    assert result["order_id"] == "test-order-123"
    assert "tracking_number" in result
    assert result["tracking_number"].startswith("TRK")
    assert "carrier" in result
    assert result["carrier"] in ["FedEx", "UPS", "USPS", "DHL"]
    assert "estimated_delivery_date" in result


@pytest.mark.asyncio
async def test_schedule_shipping_failure(mock_shipping_service, sample_shipping_data):
    """Test shipping scheduling failure"""
    # Mock shipping scheduling failure
    mock_shipping_service._simulate_shipping_scheduling = MagicMock(return_value=False)

    # Mock database insertion
    mock_shipping_service.db[mock_shipping_service.shipments_collection].insert_one = (
        AsyncMock()
    )

    # Schedule shipping - should raise exception
    with pytest.raises(Exception) as exc_info:
        await mock_shipping_service.schedule_shipping(sample_shipping_data)

    assert "Failed to schedule shipping" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_shipping_success(mock_shipping_service):
    """Test successful shipping retrieval"""
    shipping_id = "test-shipping-123"

    # Mock database response
    mock_shipping_data = {
        "shipping_id": shipping_id,
        "order_id": "test-order-123",
        "customer_id": "test-customer-123",
        "address": {
            "street": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
        },
        "items": [{"product_id": "prod-1", "quantity": 2}],
        "method": "STANDARD",
        "status": "SCHEDULED",
        "tracking_number": "TRK123456789012",
        "carrier": "FedEx",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }

    mock_shipping_service.db[
        mock_shipping_service.shipments_collection
    ].find_one.return_value = mock_shipping_data

    # Get shipping
    shipping = await mock_shipping_service.get_shipping(shipping_id)

    # Assertions
    assert shipping is not None
    assert shipping["shipping_id"] == shipping_id
    assert shipping["status"] == "SCHEDULED"
    assert shipping["tracking_number"] == "TRK123456789012"


@pytest.mark.asyncio
async def test_get_shipping_not_found(mock_shipping_service):
    """Test shipping retrieval when shipping doesn't exist"""
    shipping_id = "non-existent-shipping"

    # Mock database response (no shipping found)
    mock_shipping_service.db[
        mock_shipping_service.shipments_collection
    ].find_one.return_value = None

    # Get shipping
    shipping = await mock_shipping_service.get_shipping(shipping_id)

    # Assertions
    assert shipping is None


@pytest.mark.asyncio
async def test_cancel_shipping_success(mock_shipping_service):
    """Test successful shipping cancellation"""
    shipping_id = "test-shipping-123"
    order_id = "test-order-123"

    # Mock existing shipping
    existing_shipping = {
        "shipping_id": shipping_id,
        "order_id": order_id,
        "status": "SCHEDULED",
        "tracking_number": "TRK123456789012",
    }

    # Mock updated shipping after cancellation
    cancelled_shipping = {
        "shipping_id": shipping_id,
        "order_id": order_id,
        "status": "CANCELLED",
        "tracking_number": "TRK123456789012",
        "cancellation_reason": "Order cancelled",
    }

    # Mock database responses
    mock_shipping_service.db[
        mock_shipping_service.shipments_collection
    ].find_one.side_effect = [
        existing_shipping,  # First call (check if exists)
        cancelled_shipping,  # Second call (get updated shipping)
    ]

    mock_update_result = MagicMock()
    mock_update_result.modified_count = 1
    mock_shipping_service.db[
        mock_shipping_service.shipments_collection
    ].update_one.return_value = mock_update_result

    # Cancel shipping
    cancel_data = {
        "shipping_id": shipping_id,
        "order_id": order_id,
        "reason": "Order cancelled",
    }

    result = await mock_shipping_service.cancel_shipping(cancel_data)

    # Assertions
    assert result["success"] is True
    assert result["shipping_id"] == shipping_id
    assert result["order_id"] == order_id
    assert result["status"] == ShippingStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_cancel_shipping_not_found(mock_shipping_service):
    """Test cancellation when shipping doesn't exist"""
    shipping_id = "non-existent-shipping"
    order_id = "test-order-123"

    # Mock database response (no shipping found)
    mock_shipping_service.db[
        mock_shipping_service.shipments_collection
    ].find_one.return_value = None

    # Cancel shipping
    cancel_data = {
        "shipping_id": shipping_id,
        "order_id": order_id,
    }

    result = await mock_shipping_service.cancel_shipping(cancel_data)

    # Assertions
    assert result["success"] is False
    assert f"Shipping {shipping_id} not found" in result["message"]


@pytest.mark.asyncio
async def test_cancel_shipping_invalid_status(mock_shipping_service):
    """Test cancellation when shipping cannot be cancelled"""
    shipping_id = "test-shipping-123"
    order_id = "test-order-123"

    # Mock existing shipping with invalid status
    existing_shipping = {
        "shipping_id": shipping_id,
        "order_id": order_id,
        "status": "DELIVERED",  # Cannot cancel delivered shipping
    }

    # Mock database responses
    mock_shipping_service.db[
        mock_shipping_service.shipments_collection
    ].find_one.return_value = existing_shipping

    # Cancel shipping
    cancel_data = {
        "shipping_id": shipping_id,
        "order_id": order_id,
    }

    result = await mock_shipping_service.cancel_shipping(cancel_data)

    # Assertions
    assert result["success"] is False
    assert "cannot be cancelled" in result["message"]


@pytest.mark.asyncio
async def test_update_shipping_status_success(mock_shipping_service):
    """Test successful shipping status update"""
    shipping_id = "test-shipping-123"

    # Mock updated shipping
    updated_shipping = {
        "shipping_id": shipping_id,
        "status": "IN_TRANSIT",
        "updated_at": datetime.now(),
    }

    # Mock database responses
    mock_update_result = MagicMock()
    mock_update_result.modified_count = 1
    mock_shipping_service.db[
        mock_shipping_service.shipments_collection
    ].update_one.return_value = mock_update_result
    mock_shipping_service.db[
        mock_shipping_service.shipments_collection
    ].find_one.return_value = updated_shipping

    # Update shipping status
    result = await mock_shipping_service.update_shipping_status(
        shipping_id, ShippingStatus.IN_TRANSIT, {"location": "New York"}
    )

    # Assertions
    assert result is not None
    assert result["shipping_id"] == shipping_id
    assert result["status"] == "IN_TRANSIT"


@pytest.mark.asyncio
async def test_update_shipping_status_not_found(mock_shipping_service):
    """Test status update when shipping doesn't exist"""
    shipping_id = "non-existent-shipping"

    # Mock database response (no update)
    mock_update_result = MagicMock()
    mock_update_result.modified_count = 0
    mock_shipping_service.db[
        mock_shipping_service.shipments_collection
    ].update_one.return_value = mock_update_result

    # Update shipping status
    result = await mock_shipping_service.update_shipping_status(
        shipping_id, ShippingStatus.IN_TRANSIT
    )

    # Assertions
    assert result is None


@pytest.mark.asyncio
async def test_list_shipments(mock_shipping_service):
    """Test listing shipments with filtering"""
    # Mock database response
    mock_shipments = [
        {
            "shipping_id": "shipping-1",
            "customer_id": "customer-123",
            "status": "SCHEDULED",
            "tracking_number": "TRK123",
        },
        {
            "shipping_id": "shipping-2",
            "customer_id": "customer-123",
            "status": "IN_TRANSIT",
            "tracking_number": "TRK456",
        },
    ]

    # Mock cursor
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = mock_shipments

    mock_shipping_service.db[
        mock_shipping_service.shipments_collection
    ].find.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor

    # List shipments
    shipments = await mock_shipping_service.list_shipments(
        customer_id="customer-123", status=ShippingStatus.SCHEDULED, limit=10, skip=0
    )

    # Assertions
    assert len(shipments) == 2
    assert shipments[0]["shipping_id"] == "shipping-1"
    assert shipments[1]["shipping_id"] == "shipping-2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

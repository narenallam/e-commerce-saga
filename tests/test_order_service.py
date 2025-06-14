import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Add src to path for imports
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from services.order.service import OrderService
from services.order.models import (
    OrderCreateRequest,
    OrderStatus,
    OrderStatusUpdate,
    OrderItem,
    Address,
    PaymentMethod,
    ShippingMethod,
)


@pytest.fixture
def mock_order_service():
    """Create a mock order service for testing"""
    service = OrderService()
    service.db = AsyncMock()
    service.collection_name = "orders"
    return service


@pytest.fixture
def sample_order_request():
    """Create a sample order request for testing"""
    return OrderCreateRequest(
        customer_id="test-customer-123",
        items=[
            OrderItem(
                product_id="prod-1",
                name="Test Product",
                sku="TEST-001",
                quantity=2,
                unit_price=99.99,
                total_price=199.98,
            )
        ],
        total_amount=199.98,
        currency="USD",
        shipping_address=Address(
            street="123 Test St",
            city="Test City",
            state="TS",
            zip_code="12345",
            country="US",
        ),
        payment_method=PaymentMethod.CREDIT_CARD,
        shipping_method=ShippingMethod.STANDARD,
    )


@pytest.mark.asyncio
async def test_create_order_success(mock_order_service, sample_order_request):
    """Test successful order creation"""
    # Mock database response
    mock_insert_result = MagicMock()
    mock_insert_result.inserted_id = "mock_object_id"
    mock_order_service.db[
        mock_order_service.collection_name
    ].insert_one.return_value = mock_insert_result

    # Create order
    result = await mock_order_service.create_order(sample_order_request)

    # Assertions
    assert result.success is True
    assert result.order_id is not None
    assert result.message == "Order created successfully"
    assert result.order is not None
    assert result.order.customer_id == sample_order_request.customer_id
    assert result.order.status == OrderStatus.PENDING


@pytest.mark.asyncio
async def test_create_order_database_failure(mock_order_service, sample_order_request):
    """Test order creation with database failure"""
    # Mock database failure
    mock_insert_result = MagicMock()
    mock_insert_result.inserted_id = None
    mock_order_service.db[
        mock_order_service.collection_name
    ].insert_one.return_value = mock_insert_result

    # Create order
    result = await mock_order_service.create_order(sample_order_request)

    # Assertions
    assert result.success is False
    assert result.message == "Failed to create order"
    assert "Database insertion failed" in str(result.details)


@pytest.mark.asyncio
async def test_get_order_success(mock_order_service):
    """Test successful order retrieval"""
    order_id = "test-order-123"

    # Mock database response
    mock_order_data = {
        "order_id": order_id,
        "customer_id": "test-customer-123",
        "items": [
            {
                "product_id": "prod-1",
                "name": "Test Product",
                "sku": "TEST-001",
                "quantity": 2,
                "unit_price": 99.99,
                "total_price": 199.98,
            }
        ],
        "total_amount": 199.98,
        "currency": "USD",
        "status": "PENDING",
        "shipping_address": {
            "street": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
            "country": "US",
            "address_type": "SHIPPING",
        },
        "billing_address": {
            "street": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
            "country": "US",
            "address_type": "SHIPPING",
        },
        "payment_method": "CREDIT_CARD",
        "shipping_method": "STANDARD",
        "order_date": datetime.now(),
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "metadata": {},
    }

    mock_order_service.db[mock_order_service.collection_name].find_one.return_value = (
        mock_order_data
    )

    # Get order
    order = await mock_order_service.get_order(order_id)

    # Assertions
    assert order is not None
    assert order.order_id == order_id
    assert order.customer_id == "test-customer-123"
    assert order.status == OrderStatus.PENDING


@pytest.mark.asyncio
async def test_get_order_not_found(mock_order_service):
    """Test order retrieval when order doesn't exist"""
    order_id = "non-existent-order"

    # Mock database response (no order found)
    mock_order_service.db[mock_order_service.collection_name].find_one.return_value = (
        None
    )

    # Get order
    order = await mock_order_service.get_order(order_id)

    # Assertions
    assert order is None


@pytest.mark.asyncio
async def test_update_order_status_success(mock_order_service):
    """Test successful order status update"""
    order_id = "test-order-123"

    # Mock existing order
    existing_order_data = {
        "order_id": order_id,
        "customer_id": "test-customer-123",
        "items": [],
        "total_amount": 199.98,
        "currency": "USD",
        "status": "PENDING",
        "shipping_address": {
            "street": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
            "country": "US",
            "address_type": "SHIPPING",
        },
        "billing_address": {
            "street": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
            "country": "US",
            "address_type": "SHIPPING",
        },
        "payment_method": "CREDIT_CARD",
        "shipping_method": "STANDARD",
        "order_date": datetime.now(),
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "metadata": {},
    }

    # Updated order data
    updated_order_data = existing_order_data.copy()
    updated_order_data["status"] = "CONFIRMED"

    # Mock database responses
    mock_order_service.db[mock_order_service.collection_name].find_one.side_effect = [
        existing_order_data,  # First call (check if exists)
        updated_order_data,  # Second call (get updated order)
    ]

    mock_update_result = MagicMock()
    mock_update_result.modified_count = 1
    mock_order_service.db[
        mock_order_service.collection_name
    ].update_one.return_value = mock_update_result

    # Update order status
    status_update = OrderStatusUpdate(
        status=OrderStatus.CONFIRMED,
        reason="Payment confirmed",
        updated_by="test-system",
    )

    result = await mock_order_service.update_order_status(order_id, status_update)

    # Assertions
    assert result.success is True
    assert result.order_id == order_id
    assert "Order status updated to CONFIRMED" in result.message
    assert result.order.status == OrderStatus.CONFIRMED


@pytest.mark.asyncio
async def test_update_order_status_not_found(mock_order_service):
    """Test order status update when order doesn't exist"""
    order_id = "non-existent-order"

    # Mock database response (no order found)
    mock_order_service.db[mock_order_service.collection_name].find_one.return_value = (
        None
    )

    # Update order status
    status_update = OrderStatusUpdate(
        status=OrderStatus.CONFIRMED,
        reason="Test update",
    )

    result = await mock_order_service.update_order_status(order_id, status_update)

    # Assertions
    assert result.success is False
    assert f"Order {order_id} not found" in result.message


@pytest.mark.asyncio
async def test_cancel_order_success(mock_order_service):
    """Test successful order cancellation"""
    order_id = "test-order-123"

    # Mock existing order
    existing_order_data = {
        "order_id": order_id,
        "customer_id": "test-customer-123",
        "items": [],
        "total_amount": 199.98,
        "currency": "USD",
        "status": "PENDING",
        "shipping_address": {
            "street": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
            "country": "US",
            "address_type": "SHIPPING",
        },
        "billing_address": {
            "street": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
            "country": "US",
            "address_type": "SHIPPING",
        },
        "payment_method": "CREDIT_CARD",
        "shipping_method": "STANDARD",
        "order_date": datetime.now(),
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "metadata": {},
    }

    # Cancelled order data
    cancelled_order_data = existing_order_data.copy()
    cancelled_order_data["status"] = "CANCELLED"

    # Mock database responses
    mock_order_service.db[mock_order_service.collection_name].find_one.side_effect = [
        existing_order_data,  # First call (check if exists for cancellation)
        existing_order_data,  # Second call (check if exists for status update)
        cancelled_order_data,  # Third call (get updated order)
    ]

    mock_update_result = MagicMock()
    mock_update_result.modified_count = 1
    mock_order_service.db[
        mock_order_service.collection_name
    ].update_one.return_value = mock_update_result

    # Cancel order
    result = await mock_order_service.cancel_order(order_id, "User requested")

    # Assertions
    assert result.success is True
    assert result.order_id == order_id
    assert "Order status updated to CANCELLED" in result.message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

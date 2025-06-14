import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Add src to path for imports
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from services.inventory.service import InventoryService
from services.inventory.models import InventoryStatus


@pytest.fixture
def mock_inventory_service():
    """Create a mock inventory service for testing"""
    service = InventoryService()
    service.db = AsyncMock()
    service.inventory_collection = "inventory"
    service.reservations_collection = "inventory_reservations"
    return service


@pytest.fixture
def sample_product_data():
    """Create sample product data for testing"""
    return {
        "product_id": "test-product-123",
        "name": "Test Product",
        "description": "A test product",
        "sku": "TEST-001",
        "quantity": 100,
        "reserved_quantity": 10,
        "status": "AVAILABLE",
        "price": 99.99,
        "category": "Electronics",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }


@pytest.fixture
def sample_order_items():
    """Create sample order items for testing"""
    return [
        {
            "product_id": "test-product-123",
            "name": "Test Product",
            "quantity": 5,
            "unit_price": 99.99,
            "total_price": 499.95,
        },
        {
            "product_id": "test-product-456",
            "name": "Another Product",
            "quantity": 2,
            "unit_price": 49.99,
            "total_price": 99.98,
        },
    ]


@pytest.mark.asyncio
async def test_get_product_success(mock_inventory_service, sample_product_data):
    """Test successful product retrieval"""
    product_id = "test-product-123"

    # Mock database response
    mock_inventory_service.db[
        mock_inventory_service.inventory_collection
    ].find_one.return_value = sample_product_data

    # Get product
    product = await mock_inventory_service.get_product(product_id)

    # Assertions
    assert product is not None
    assert product["product_id"] == product_id
    assert product["name"] == "Test Product"
    assert product["quantity"] == 100


@pytest.mark.asyncio
async def test_get_product_not_found(mock_inventory_service):
    """Test product retrieval when product doesn't exist"""
    product_id = "non-existent-product"

    # Mock database response (no product found)
    mock_inventory_service.db[
        mock_inventory_service.inventory_collection
    ].find_one.return_value = None

    # Get product
    product = await mock_inventory_service.get_product(product_id)

    # Assertions
    assert product is None


@pytest.mark.asyncio
async def test_list_inventory_success(mock_inventory_service, sample_product_data):
    """Test successful inventory listing"""
    # Mock database response
    mock_products = [sample_product_data]

    # Mock cursor
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = mock_products

    mock_inventory_service.db[
        mock_inventory_service.inventory_collection
    ].find.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor

    # List inventory
    products = await mock_inventory_service.list_inventory(
        status=InventoryStatus.AVAILABLE, limit=10, skip=0
    )

    # Assertions
    assert len(products) == 1
    assert products[0]["product_id"] == "test-product-123"


@pytest.mark.asyncio
async def test_reserve_inventory_success(
    mock_inventory_service, sample_product_data, sample_order_items
):
    """Test successful inventory reservation"""
    order_id = "test-order-123"

    # Mock database responses
    mock_inventory_service.get_product = AsyncMock(return_value=sample_product_data)
    mock_inventory_service.db[
        mock_inventory_service.inventory_collection
    ].update_one = AsyncMock()
    mock_inventory_service.db[
        mock_inventory_service.reservations_collection
    ].insert_one = AsyncMock()

    # Reserve inventory
    result = await mock_inventory_service.reserve_inventory(
        order_id, sample_order_items
    )

    # Assertions
    assert result["success"] is True
    assert result["order_id"] == order_id
    assert len(result["reservations"]) == 2  # Two items reserved
    assert "Successfully reserved" in result["message"]


@pytest.mark.asyncio
async def test_reserve_inventory_insufficient_stock(
    mock_inventory_service, sample_order_items
):
    """Test inventory reservation with insufficient stock"""
    order_id = "test-order-123"

    # Mock product with low stock
    low_stock_product = {
        "product_id": "test-product-123",
        "quantity": 2,  # Only 2 available
        "reserved_quantity": 0,
    }

    # Mock database responses - first item has insufficient stock
    mock_inventory_service.get_product = AsyncMock(
        side_effect=[
            low_stock_product,  # First product (insufficient stock)
            None,  # Second product (not found)
        ]
    )

    # Reserve inventory
    result = await mock_inventory_service.reserve_inventory(
        order_id, sample_order_items
    )

    # Assertions
    assert result["success"] is False
    assert "Some items could not be reserved" in result["message"]
    assert len(result["failed_items"]) == 2  # Both items failed


@pytest.mark.asyncio
async def test_reserve_inventory_product_not_found(
    mock_inventory_service, sample_order_items
):
    """Test inventory reservation when product doesn't exist"""
    order_id = "test-order-123"

    # Mock database responses - products not found
    mock_inventory_service.get_product = AsyncMock(return_value=None)

    # Reserve inventory
    result = await mock_inventory_service.reserve_inventory(
        order_id, sample_order_items
    )

    # Assertions
    assert result["success"] is False
    assert len(result["failed_items"]) == 2
    assert "not found" in result["failed_items"][0]["reason"]


@pytest.mark.asyncio
async def test_release_inventory_success(mock_inventory_service):
    """Test successful inventory release"""
    order_id = "test-order-123"

    # Mock existing reservations
    mock_reservations = [
        {
            "reservation_id": "res-1",
            "product_id": "prod-1",
            "quantity": 5,
            "order_id": order_id,
        },
        {
            "reservation_id": "res-2",
            "product_id": "prod-2",
            "quantity": 2,
            "order_id": order_id,
        },
    ]

    # Mock cursor for reservations
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = mock_reservations

    mock_inventory_service.db[
        mock_inventory_service.reservations_collection
    ].find.return_value = mock_cursor
    mock_inventory_service.db[
        mock_inventory_service.inventory_collection
    ].update_one = AsyncMock()
    mock_inventory_service.db[
        mock_inventory_service.reservations_collection
    ].delete_one = AsyncMock()

    # Release inventory
    result = await mock_inventory_service.release_inventory(order_id)

    # Assertions
    assert result["success"] is True
    assert result["order_id"] == order_id
    assert result["released_count"] == 2
    assert "Released 2 reservations" in result["message"]


@pytest.mark.asyncio
async def test_release_inventory_no_reservations(mock_inventory_service):
    """Test inventory release when no reservations exist"""
    order_id = "test-order-123"

    # Mock cursor with no reservations
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = []

    mock_inventory_service.db[
        mock_inventory_service.reservations_collection
    ].find.return_value = mock_cursor

    # Release inventory
    result = await mock_inventory_service.release_inventory(order_id)

    # Assertions
    assert result["success"] is True
    assert result["order_id"] == order_id
    assert "No reservations found" in result["message"]


@pytest.mark.asyncio
async def test_release_inventory_with_reservation_id(mock_inventory_service):
    """Test inventory release with specific reservation ID"""
    order_id = "test-order-123"
    reservation_id = "res-1"

    # Mock specific reservation
    mock_reservations = [
        {
            "reservation_id": reservation_id,
            "product_id": "prod-1",
            "quantity": 5,
            "order_id": order_id,
        }
    ]

    # Mock cursor for reservations
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = mock_reservations

    mock_inventory_service.db[
        mock_inventory_service.reservations_collection
    ].find.return_value = mock_cursor
    mock_inventory_service.db[
        mock_inventory_service.inventory_collection
    ].update_one = AsyncMock()
    mock_inventory_service.db[
        mock_inventory_service.reservations_collection
    ].delete_one = AsyncMock()

    # Release inventory with specific reservation ID
    result = await mock_inventory_service.release_inventory(order_id, reservation_id)

    # Assertions
    assert result["success"] is True
    assert result["released_count"] == 1


@pytest.mark.asyncio
async def test_list_inventory_with_status_filter(mock_inventory_service):
    """Test inventory listing with status filtering"""
    # Mock database response
    mock_products = [
        {"product_id": "prod-1", "status": "AVAILABLE"},
        {"product_id": "prod-2", "status": "AVAILABLE"},
    ]

    # Mock cursor
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = mock_products

    mock_inventory_service.db[
        mock_inventory_service.inventory_collection
    ].find.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor

    # List inventory with status filter
    products = await mock_inventory_service.list_inventory(
        status=InventoryStatus.AVAILABLE, limit=100, skip=0
    )

    # Verify query was called with status filter
    expected_query = {"status": "AVAILABLE"}
    mock_inventory_service.db[
        mock_inventory_service.inventory_collection
    ].find.assert_called_with(expected_query)

    # Assertions
    assert len(products) == 2
    assert all(p["status"] == "AVAILABLE" for p in products)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Add src to path for imports
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from services.payment.service import PaymentService
from services.payment.models import PaymentStatus, PaymentMethod


@pytest.fixture
def mock_payment_service():
    """Create a mock payment service for testing"""
    service = PaymentService()
    service.db = AsyncMock()
    service.payments_collection = "payments"
    service.refunds_collection = "refunds"
    return service


@pytest.fixture
def sample_payment_data():
    """Create sample payment data for testing"""
    return {
        "order_id": "test-order-123",
        "customer_id": "test-customer-123",
        "amount": 199.99,
        "currency": "USD",
        "payment_method": "CREDIT_CARD",
        "order_data": {
            "order_id": "test-order-123",
            "customer_id": "test-customer-123",
            "total_amount": 199.99,
        },
    }


@pytest.mark.asyncio
async def test_process_payment_success(mock_payment_service, sample_payment_data):
    """Test successful payment processing"""
    # Mock successful payment processing
    mock_payment_service._simulate_payment_processing = MagicMock(return_value=True)

    # Mock database insertion
    mock_payment_service.db[mock_payment_service.payments_collection].insert_one = (
        AsyncMock()
    )

    # Process payment
    result = await mock_payment_service.process_payment(sample_payment_data)

    # Assertions
    assert result["status"] == PaymentStatus.COMPLETED.value
    assert result["order_id"] == "test-order-123"
    assert result["amount"] == 199.99
    assert "transaction_reference" in result
    assert result["transaction_reference"].startswith("TX-")


@pytest.mark.asyncio
async def test_process_payment_failure(mock_payment_service, sample_payment_data):
    """Test payment processing failure"""
    # Mock payment processing failure
    mock_payment_service._simulate_payment_processing = MagicMock(return_value=False)

    # Mock database insertion
    mock_payment_service.db[mock_payment_service.payments_collection].insert_one = (
        AsyncMock()
    )

    # Process payment - should raise exception
    with pytest.raises(Exception) as exc_info:
        await mock_payment_service.process_payment(sample_payment_data)

    assert "Payment processing failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_payment_success(mock_payment_service):
    """Test successful payment retrieval"""
    payment_id = "test-payment-123"

    # Mock database response
    mock_payment_data = {
        "payment_id": payment_id,
        "order_id": "test-order-123",
        "customer_id": "test-customer-123",
        "amount": 199.99,
        "currency": "USD",
        "payment_method": "CREDIT_CARD",
        "status": "COMPLETED",
        "transaction_reference": "TX-12345678",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }

    mock_payment_service.db[
        mock_payment_service.payments_collection
    ].find_one.return_value = mock_payment_data

    # Get payment
    payment = await mock_payment_service.get_payment(payment_id)

    # Assertions
    assert payment is not None
    assert payment["payment_id"] == payment_id
    assert payment["status"] == "COMPLETED"
    assert payment["amount"] == 199.99


@pytest.mark.asyncio
async def test_get_payment_not_found(mock_payment_service):
    """Test payment retrieval when payment doesn't exist"""
    payment_id = "non-existent-payment"

    # Mock database response (no payment found)
    mock_payment_service.db[
        mock_payment_service.payments_collection
    ].find_one.return_value = None

    # Get payment
    payment = await mock_payment_service.get_payment(payment_id)

    # Assertions
    assert payment is None


@pytest.mark.asyncio
async def test_refund_payment_success(mock_payment_service):
    """Test successful payment refund"""
    payment_id = "test-payment-123"
    order_id = "test-order-123"

    # Mock existing payment
    existing_payment = {
        "payment_id": payment_id,
        "order_id": order_id,
        "amount": 199.99,
        "status": "COMPLETED",
    }

    # Mock database responses
    mock_payment_service.db[
        mock_payment_service.payments_collection
    ].find_one.return_value = existing_payment
    mock_payment_service.db[mock_payment_service.refunds_collection].insert_one = (
        AsyncMock()
    )

    mock_update_result = MagicMock()
    mock_update_result.modified_count = 1
    mock_payment_service.db[
        mock_payment_service.payments_collection
    ].update_one.return_value = mock_update_result

    # Refund payment
    refund_data = {
        "payment_id": payment_id,
        "order_id": order_id,
        "reason": "Customer requested refund",
    }

    result = await mock_payment_service.refund_payment(refund_data)

    # Assertions
    assert result["success"] is True
    assert result["payment_id"] == payment_id
    assert result["order_id"] == order_id
    assert result["amount"] == 199.99
    assert result["status"] == PaymentStatus.REFUNDED.value


@pytest.mark.asyncio
async def test_refund_payment_not_found(mock_payment_service):
    """Test refund when payment doesn't exist"""
    payment_id = "non-existent-payment"
    order_id = "test-order-123"

    # Mock database response (no payment found)
    mock_payment_service.db[
        mock_payment_service.payments_collection
    ].find_one.return_value = None

    # Refund payment
    refund_data = {
        "payment_id": payment_id,
        "order_id": order_id,
    }

    result = await mock_payment_service.refund_payment(refund_data)

    # Assertions
    assert result["success"] is False
    assert f"Payment {payment_id} not found" in result["message"]


@pytest.mark.asyncio
async def test_refund_payment_invalid_status(mock_payment_service):
    """Test refund when payment cannot be refunded"""
    payment_id = "test-payment-123"
    order_id = "test-order-123"

    # Mock existing payment with invalid status
    existing_payment = {
        "payment_id": payment_id,
        "order_id": order_id,
        "amount": 199.99,
        "status": "PENDING",  # Cannot refund pending payment
    }

    # Mock database responses
    mock_payment_service.db[
        mock_payment_service.payments_collection
    ].find_one.return_value = existing_payment

    # Refund payment
    refund_data = {
        "payment_id": payment_id,
        "order_id": order_id,
    }

    result = await mock_payment_service.refund_payment(refund_data)

    # Assertions
    assert result["success"] is False
    assert "cannot be refunded" in result["message"]


@pytest.mark.asyncio
async def test_list_payments(mock_payment_service):
    """Test listing payments with filtering"""
    # Mock database response
    mock_payments = [
        {
            "payment_id": "payment-1",
            "customer_id": "customer-123",
            "status": "COMPLETED",
            "amount": 99.99,
        },
        {
            "payment_id": "payment-2",
            "customer_id": "customer-123",
            "status": "PENDING",
            "amount": 149.99,
        },
    ]

    # Mock cursor
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = mock_payments

    mock_payment_service.db[
        mock_payment_service.payments_collection
    ].find.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor

    # List payments
    payments = await mock_payment_service.list_payments(
        customer_id="customer-123", status=PaymentStatus.COMPLETED, limit=10, skip=0
    )

    # Assertions
    assert len(payments) == 2
    assert payments[0]["payment_id"] == "payment-1"
    assert payments[1]["payment_id"] == "payment-2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

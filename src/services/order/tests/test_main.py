import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_metrics_endpoint():
    """Test metrics endpoint"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.json() == {"status": "metrics endpoint"}


@pytest.mark.asyncio
async def test_database_connection():
    """Test database connection"""
    from common.database import Database

    db = await Database.connect("order")
    assert db is not None
    await Database.close()


def test_request_metrics():
    """Test request metrics collection"""
    # Make a request
    client.get("/health")

    # Check if metrics were collected
    response = client.get("/metrics")
    assert response.status_code == 200
    # Add more specific metric assertions here

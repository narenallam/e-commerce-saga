import sys
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Body
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from prometheus_client import make_asgi_app, Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
import time

from pathlib import Path

# Add parent directory to path to import common modules
sys.path.append(str(Path(__file__).resolve().parents[2]))

from common.database import Database
from .models import (
    OrderCreateRequest,
    OrderResponse,
    OrderStatusUpdate,
    OrderStatus,
    Order,
)
from .service import OrderService

order_service = OrderService()

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"]
)
REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds", "Request latency", ["endpoint"]
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        REQUEST_COUNT.labels(
            request.method, request.url.path, response.status_code
        ).inc()
        REQUEST_LATENCY.labels(request.url.path).observe(process_time)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    await order_service.initialize()
    yield
    await Database.close()


app = FastAPI(title="Order Service", lifespan=lifespan)
app.add_middleware(PrometheusMiddleware)
app.mount("/metrics", make_asgi_app())


@app.get("/")
async def root():
    return {"message": "Order Service API", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/orders", response_model=List[Order])
async def list_orders(
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
):
    """List orders with optional filtering"""
    status_enum = None
    if status:
        try:
            status_enum = OrderStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    orders = await order_service.list_orders(customer_id, status_enum, limit, skip)
    return orders


@app.get("/api/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    """Get order by ID"""
    order = await order_service.get_order(order_id)

    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    return order


@app.post("/api/orders", response_model=OrderResponse)
async def create_order(order_request: OrderCreateRequest):
    """Create a new order"""
    try:
        result = await order_service.create_order(order_request)

        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/orders/{order_id}/status", response_model=OrderResponse)
async def update_order_status(order_id: str, status_update: OrderStatusUpdate):
    """Update order status"""
    try:
        result = await order_service.update_order_status(order_id, status_update)

        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/orders/{order_id}", response_model=OrderResponse)
async def cancel_order(order_id: str, reason: str = "User requested"):
    """Cancel an order"""
    try:
        result = await order_service.cancel_order(order_id, reason)

        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/orders/create", response_model=OrderResponse)
async def create_order_saga(data: Dict[str, Any] = Body(...)):
    """Create an order (called by saga orchestrator)"""
    try:
        # Convert dict to OrderCreateRequest
        order_request = OrderCreateRequest(**data)
        result = await order_service.create_order(order_request)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/orders/cancel", response_model=OrderResponse)
async def cancel_order_saga(data: Dict[str, Any] = Body(...)):
    """Cancel an order (called by saga orchestrator for compensation)"""
    try:
        order_id = data.get("order_id")
        reason = data.get("reason", "Saga compensation")

        if not order_id:
            raise HTTPException(status_code=400, detail="order_id is required")

        result = await order_service.cancel_order(order_id, reason)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/orders/statistics")
async def get_order_statistics():
    """Get order statistics and metrics"""
    try:
        stats = await order_service.get_order_statistics()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving statistics: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

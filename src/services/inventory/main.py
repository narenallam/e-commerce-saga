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
    ProductInventory,
    InventoryReservationRequest,
    InventoryReservationResponse,
    InventoryReleaseRequest,
    InventoryUpdateRequest,
    InventoryStatus,
)
from .service import InventoryService

inventory_service = InventoryService()

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
    await inventory_service.initialize()
    yield
    await Database.close()


app = FastAPI(title="Inventory Service", lifespan=lifespan)
app.add_middleware(PrometheusMiddleware)
app.mount("/metrics", make_asgi_app())


@app.get("/")
async def root():
    return {"message": "Inventory Service API", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/inventory", response_model=List[ProductInventory])
async def list_inventory(status: Optional[str] = None, limit: int = 100, skip: int = 0):
    """List inventory with optional filtering"""
    status_enum = None
    if status:
        try:
            status_enum = InventoryStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    inventory = await inventory_service.list_inventory(status_enum, limit, skip)
    return inventory


@app.get("/api/inventory/{product_id}", response_model=ProductInventory)
async def get_product(product_id: str):
    """Get product from inventory by ID"""
    product = await inventory_service.get_product(product_id)

    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    return product


@app.post("/api/inventory/reserve", response_model=InventoryReservationResponse)
async def reserve_inventory(data: Dict[str, Any] = Body(...)):
    """Reserve inventory for an order (called by saga orchestrator)"""
    try:
        # Extract data from request
        order_id = data.get("order_id")
        items = data.get("items", [])

        if not order_id:
            raise HTTPException(status_code=400, detail="order_id is required")

        if not items:
            # If items not provided in this request, extract from order_data
            order_data = data.get("order_data", {})
            items = order_data.get("items", [])

        if not items:
            raise HTTPException(status_code=400, detail="No items provided to reserve")

        result = await inventory_service.reserve_inventory(order_id, items)

        # If reserve failed, raise exception to trigger saga compensation
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Failed to reserve inventory",
                    "failed_items": result.get("failed_items", []),
                },
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/inventory/release")
async def release_inventory(data: Dict[str, Any] = Body(...)):
    """Release previously reserved inventory (called by saga orchestrator for compensation)"""
    try:
        # Extract data from request
        order_id = data.get("order_id")

        if not order_id:
            # Try to get order_id from original_response if available
            original_response = data.get("original_response", {})
            order_id = original_response.get("order_id")

        if not order_id:
            raise HTTPException(status_code=400, detail="order_id is required")

        # Get reservation ID and items if available
        reservation_id = data.get("reservation_id")
        items = data.get("items")

        # If reservation_id not provided but available in original_response
        if not reservation_id and "original_response" in data:
            original_response = data.get("original_response", {})
            reservation_id = original_response.get("reservation_id")

        result = await inventory_service.release_inventory(
            order_id, reservation_id, items
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/inventory/{product_id}")
async def update_inventory(product_id: str, update: InventoryUpdateRequest):
    """Update inventory quantity"""
    if update.product_id != product_id:
        raise HTTPException(
            status_code=400, detail="Product ID in path and body must match"
        )

    updated_product = await inventory_service.update_inventory(
        product_id, update.quantity_change, update.reason
    )

    if not updated_product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    return updated_product


@app.get("/api/inventory/statistics")
async def get_inventory_statistics():
    """Get inventory statistics and metrics"""
    try:
        stats = await inventory_service.get_inventory_statistics()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving statistics: {str(e)}"
        )


@app.get("/api/inventory/cache/info")
async def get_cache_info():
    """Get cache statistics and performance info"""
    try:
        if inventory_service.cache_service:
            cache_info = await inventory_service.cache_service.get_cache_info()
            return {
                "cache_status": cache_info,
                "service": "inventory",
                "cache_enabled": inventory_service.settings.cache_enabled,
            }
        else:
            return {
                "cache_status": "disabled",
                "service": "inventory",
                "cache_enabled": False,
            }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving cache info: {str(e)}"
        )


@app.post("/api/inventory/cache/clear")
async def clear_cache():
    """Clear all cache entries for inventory service"""
    try:
        if inventory_service.cache_service:
            cleared_count = await inventory_service.cache_service.clear_service_cache()
            return {
                "message": f"Cleared {cleared_count} cache entries",
                "service": "inventory",
            }
        else:
            return {"message": "Cache not enabled", "service": "inventory"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")


@app.get("/metrics")
async def metrics():
    """Metrics endpoint for monitoring"""
    return {"status": "metrics endpoint", "service": "inventory-service"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)

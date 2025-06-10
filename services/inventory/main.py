import sys
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Body
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

# Add parent directory to path to import common modules
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await inventory_service.initialize()
    yield
    await Database.close()


app = FastAPI(title="Inventory Service", lifespan=lifespan)


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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)

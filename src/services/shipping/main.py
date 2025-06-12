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
    ShippingScheduleRequest,
    ShippingResponse,
    ShippingCancelRequest,
    ShippingStatus,
    ShippingMethod,
)
from .service import ShippingService

shipping_service = ShippingService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await shipping_service.initialize()
    yield
    await Database.close()


app = FastAPI(title="Shipping Service", lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Shipping Service API", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/shipping", response_model=List[ShippingResponse])
async def list_shipments(
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
):
    """List shipments with optional filtering"""
    status_enum = None
    if status:
        try:
            status_enum = ShippingStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    shipments = await shipping_service.list_shipments(
        customer_id, status_enum, limit, skip
    )
    return shipments


@app.get("/api/shipping/{shipping_id}", response_model=ShippingResponse)
async def get_shipping(shipping_id: str):
    """Get shipping by ID"""
    shipping = await shipping_service.get_shipping(shipping_id)

    if not shipping:
        raise HTTPException(status_code=404, detail=f"Shipping {shipping_id} not found")

    return shipping


@app.get("/api/shipping/order/{order_id}", response_model=ShippingResponse)
async def get_shipping_by_order(order_id: str):
    """Get shipping by order ID"""
    shipping = await shipping_service.get_shipping_by_order(order_id)

    if not shipping:
        raise HTTPException(
            status_code=404, detail=f"No shipping found for order {order_id}"
        )

    return shipping


@app.post("/api/shipping/schedule", response_model=ShippingResponse)
async def schedule_shipping(data: Dict[str, Any] = Body(...)):
    """Schedule shipping for an order (called by saga orchestrator)"""
    try:
        result = await shipping_service.schedule_shipping(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/shipping/cancel")
async def cancel_shipping(data: Dict[str, Any] = Body(...)):
    """Cancel shipping (called by saga orchestrator for compensation)"""
    try:
        result = await shipping_service.cancel_shipping(data)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message"))

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/shipping/{shipping_id}/status")
async def update_shipping_status(
    shipping_id: str, status: ShippingStatus, metadata: Optional[Dict[str, Any]] = None
):
    """Update shipping status"""
    updated_shipping = await shipping_service.update_shipping_status(
        shipping_id, status, metadata
    )

    if not updated_shipping:
        raise HTTPException(status_code=404, detail=f"Shipping {shipping_id} not found")

    return updated_shipping


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)

import sys
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Body
from typing import List, Optional, Dict, Any

# Add parent directory to path to import common modules
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from common.database import Database
from .models import (
    PaymentRequest,
    PaymentResponse,
    RefundRequest,
    RefundResponse,
    PaymentStatus,
)
from .service import PaymentService

app = FastAPI(title="Payment Service")
payment_service = PaymentService()


@app.on_event("startup")
async def startup_db_client():
    await payment_service.initialize()


@app.on_event("shutdown")
async def shutdown_db_client():
    await Database.close()


@app.get("/")
async def root():
    return {"message": "Payment Service API", "status": "running"}


@app.get("/api/payments", response_model=List[PaymentResponse])
async def list_payments(
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
):
    """List payments with optional filtering"""
    status_enum = None
    if status:
        try:
            status_enum = PaymentStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    payments = await payment_service.list_payments(
        customer_id, status_enum, limit, skip
    )
    return payments


@app.get("/api/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str):
    """Get payment by ID"""
    payment = await payment_service.get_payment(payment_id)

    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")

    return payment


@app.get("/api/payments/order/{order_id}", response_model=PaymentResponse)
async def get_payment_by_order(order_id: str):
    """Get payment by order ID"""
    payment = await payment_service.get_payment_by_order(order_id)

    if not payment:
        raise HTTPException(
            status_code=404, detail=f"No payment found for order {order_id}"
        )

    return payment


@app.post("/api/payments/process", response_model=PaymentResponse)
async def process_payment(data: Dict[str, Any] = Body(...)):
    """Process a payment (called by saga orchestrator)"""
    try:
        result = await payment_service.process_payment(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/payments/refund", response_model=RefundResponse)
async def refund_payment(data: Dict[str, Any] = Body(...)):
    """Refund a payment (called by saga orchestrator for compensation)"""
    try:
        result = await payment_service.refund_payment(data)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message"))

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)

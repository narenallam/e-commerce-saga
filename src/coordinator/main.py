import os
import sys
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Add the src directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coordinator.order_saga import OrderSaga

app = FastAPI(
    title="Saga Coordinator Service",
    description="Orchestrates distributed transactions across microservices",
    version="1.0.0",
)


# Pydantic models for API
class OrderRequest(BaseModel):
    customer_id: str
    items: list
    total_amount: float
    customer_details: Dict[str, Any] = {}


class SagaResponse(BaseModel):
    saga_id: str
    order_id: str = None
    status: str
    message: str
    details: Dict[str, Any] = {}


# In-memory storage for active sagas (in production, use Redis or database)
active_sagas: Dict[str, OrderSaga] = {}


@app.get("/")
async def root():
    return {"message": "Saga Coordinator Service", "status": "running", "port": 9000}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/coordinator/orders", response_model=SagaResponse)
async def create_order_saga(order_request: OrderRequest):
    """Create and execute a new order saga"""
    try:
        # Prepare order data for the saga
        order_data = {
            "customer_id": order_request.customer_id,
            "items": order_request.items,
            "total_amount": order_request.total_amount,
            "customer_details": order_request.customer_details,
        }

        # Create and execute the saga
        saga = OrderSaga(order_data)
        active_sagas[saga.id] = saga

        # Process the order saga
        result = await saga.process_order()

        return SagaResponse(
            saga_id=saga.id,
            order_id=result.get("order_id"),
            status=result.get("status", "unknown"),
            message=result.get("message", "Order saga initiated"),
            details=result.get("details", {}),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process order saga: {str(e)}"
        )


@app.get("/api/coordinator/orders/{saga_id}", response_model=SagaResponse)
async def get_saga_status(saga_id: str):
    """Get the status of a specific saga"""
    try:
        if saga_id not in active_sagas:
            raise HTTPException(status_code=404, detail="Saga not found")

        saga = active_sagas[saga_id]
        return SagaResponse(
            saga_id=saga.id,
            order_id=saga.context.get("order_id"),
            status=(
                saga.status.value if hasattr(saga.status, "value") else str(saga.status)
            ),
            message=f"Saga status: {saga.status}",
            details=saga.context,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get saga status: {str(e)}"
        )


@app.delete("/api/coordinator/orders/{saga_id}")
async def cancel_saga(saga_id: str):
    """Cancel a specific saga and trigger compensation"""
    try:
        if saga_id not in active_sagas:
            raise HTTPException(status_code=404, detail="Saga not found")

        saga = active_sagas[saga_id]

        # If saga is still running, trigger compensation
        compensation_result = await saga.compensate()

        # Remove from active sagas
        del active_sagas[saga_id]

        return {
            "saga_id": saga_id,
            "status": "cancelled",
            "message": "Saga cancelled and compensated",
            "compensation_result": compensation_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel saga: {str(e)}")


@app.get("/api/coordinator/sagas")
async def list_active_sagas():
    """List all active sagas"""
    return {
        "active_sagas": len(active_sagas),
        "sagas": [
            {
                "saga_id": saga_id,
                "status": (
                    saga.status.value
                    if hasattr(saga.status, "value")
                    else str(saga.status)
                ),
                "order_id": saga.context.get("order_id"),
            }
            for saga_id, saga in active_sagas.items()
        ],
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 9000))
    uvicorn.run(app, host="0.0.0.0", port=port)

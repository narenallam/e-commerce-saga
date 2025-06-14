import os
import sys
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from prometheus_client import make_asgi_app, Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
import time

# Add the src directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coordinator.order_saga import OrderSaga

app = FastAPI(
    title="Saga Coordinator Service",
    description="Orchestrates distributed transactions across microservices",
    version="1.0.0",
)

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


app.add_middleware(PrometheusMiddleware)
app.mount("/metrics", make_asgi_app())


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
    """List all active sagas with detailed information"""
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
                "steps_completed": len([s for s in saga.steps if s.is_executed]),
                "total_steps": len(saga.steps),
                "failed_step_index": (
                    saga.failed_step_index if saga.failed_step_index >= 0 else None
                ),
            }
            for saga_id, saga in active_sagas.items()
        ],
    }


@app.get("/api/coordinator/health")
async def coordinator_health_check():
    """Enhanced health check that also checks service connectivity"""
    try:
        # Import here to avoid circular imports
        from common.messaging import ServiceCommunicator

        communicator = ServiceCommunicator()
        service_health = await communicator.check_all_services_health()

        all_services_healthy = all(service_health.values())

        return {
            "coordinator_status": "healthy",
            "active_sagas": len(active_sagas),
            "services_health": service_health,
            "all_services_healthy": all_services_healthy,
            "service_urls": communicator.base_urls,
        }
    except Exception as e:
        return {
            "coordinator_status": "degraded",
            "error": str(e),
            "active_sagas": len(active_sagas),
        }


@app.get("/api/coordinator/statistics")
async def get_coordinator_statistics():
    """Get coordinator statistics and metrics"""
    try:
        # Calculate saga statistics
        total_sagas = len(active_sagas)

        status_counts = {}
        for saga in active_sagas.values():
            status = (
                saga.status.value if hasattr(saga.status, "value") else str(saga.status)
            )
            status_counts[status] = status_counts.get(status, 0) + 1

        # Calculate step completion statistics
        total_steps = sum(len(saga.steps) for saga in active_sagas.values())
        completed_steps = sum(
            len([s for s in saga.steps if s.is_executed])
            for saga in active_sagas.values()
        )

        return {
            "total_active_sagas": total_sagas,
            "status_breakdown": status_counts,
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "step_completion_rate": (
                (completed_steps / total_steps * 100) if total_steps > 0 else 0
            ),
            "average_steps_per_saga": (
                total_steps / total_sagas if total_sagas > 0 else 0
            ),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving statistics: {str(e)}"
        )


@app.get("/metrics")
async def metrics():
    """Metrics endpoint for monitoring systems"""
    return {"status": "metrics endpoint", "service": "saga-coordinator"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 9000))
    uvicorn.run(app, host="0.0.0.0", port=port)

import sys
import os
import uuid
from datetime import datetime
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
    NotificationRequest,
    NotificationResponse,
    NotificationStatus,
    NotificationType,
    NotificationChannel,
)
from .service import NotificationService

notification_service = NotificationService()

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
    await notification_service.initialize()
    yield
    await Database.close()


app = FastAPI(title="Notification Service", lifespan=lifespan)
app.add_middleware(PrometheusMiddleware)
app.mount("/metrics", make_asgi_app())


@app.get("/")
async def root():
    return {"message": "Notification Service API", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/notifications", response_model=List[NotificationResponse])
async def list_notifications(
    customer_id: Optional[str] = None,
    order_id: Optional[str] = None,
    status: Optional[str] = None,
    notification_type: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
):
    """List notifications with optional filtering"""
    status_enum = None
    if status:
        try:
            status_enum = NotificationStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    type_enum = None
    if notification_type:
        try:
            type_enum = NotificationType(notification_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid notification type: {notification_type}",
            )

    notifications = await notification_service.list_notifications(
        customer_id, order_id, status_enum, type_enum, limit, skip
    )
    return notifications


@app.get("/api/notifications/{notification_id}", response_model=NotificationResponse)
async def get_notification(notification_id: str):
    """Get notification by ID"""
    notification = await notification_service.get_notification(notification_id)

    if not notification:
        raise HTTPException(
            status_code=404, detail=f"Notification {notification_id} not found"
        )

    return notification


@app.post("/api/notifications/send", response_model=NotificationResponse)
async def send_notification(data: Dict[str, Any] = Body(...)):
    """Send a notification (called by saga orchestrator)"""
    try:
        result = await notification_service.send_notification(data)
        return result
    except Exception as e:
        # Note: We don't fail the saga if notification fails
        # Just log the error and return it
        result = {
            "notification_id": str(uuid.uuid4()),
            "status": NotificationStatus.FAILED.value,
            "error_message": str(e),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        # Add minimum required fields from the request
        for field in ["notification_type", "customer_id", "order_id", "channels"]:
            if field in data:
                result[field] = data[field]

        return result


@app.post("/api/notifications/cancel")
async def cancel_notification(data: Dict[str, Any] = Body(...)):
    """Cancel a notification if possible (called by saga orchestrator for compensation)"""
    result = await notification_service.cancel_notification(data)
    return result


@app.get("/api/notifications/statistics")
async def get_notification_statistics():
    """Get notification statistics and metrics"""
    try:
        stats = await notification_service.get_notification_statistics()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving statistics: {str(e)}"
        )


@app.get("/api/notifications/cache/info")
async def get_cache_info():
    """Get cache statistics and performance info"""
    try:
        if notification_service.cache_service:
            cache_info = await notification_service.cache_service.get_cache_info()
            return {
                "cache_status": cache_info,
                "service": "notification",
                "cache_enabled": notification_service.settings.cache_enabled,
            }
        else:
            return {
                "cache_status": "disabled",
                "service": "notification",
                "cache_enabled": False,
            }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving cache info: {str(e)}"
        )


@app.post("/api/notifications/cache/clear")
async def clear_cache():
    """Clear all cache entries for notification service"""
    try:
        if notification_service.cache_service:
            cleared_count = (
                await notification_service.cache_service.clear_service_cache()
            )
            return {
                "message": f"Cleared {cleared_count} cache entries",
                "service": "notification",
            }
        else:
            return {"message": "Cache not enabled", "service": "notification"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")


@app.get("/metrics")
async def metrics():
    """Metrics endpoint for monitoring"""
    return {"status": "metrics endpoint", "service": "notification-service"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)

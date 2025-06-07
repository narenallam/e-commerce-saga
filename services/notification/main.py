import sys
import os
import uuid
from datetime import datetime
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
    NotificationRequest,
    NotificationResponse,
    NotificationStatus,
    NotificationType,
    NotificationChannel,
)
from .service import NotificationService

notification_service = NotificationService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await notification_service.initialize()
    yield
    await Database.close()


app = FastAPI(title="Notification Service", lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Notification Service API", "status": "running"}


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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)

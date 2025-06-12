import sys
import os
import uuid
import random
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add parent directory to path to import common modules
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from common.database import Database
from .models import NotificationStatus, NotificationType, NotificationChannel


class NotificationService:
    """Service for handling notification operations"""

    def __init__(self):
        self.notifications_collection = "notifications"
        self.templates_collection = "notification_templates"
        self.db = None

    async def initialize(self):
        """Initialize the database connection"""
        self.db = await Database.connect("notification")

        # Create templates if not exist
        if await self.db[self.templates_collection].count_documents({}) == 0:
            await self._create_sample_templates()

    async def _create_sample_templates(self):
        """Create sample notification templates"""
        templates = [
            {
                "template_id": "order_confirmation_email",
                "notification_type": NotificationType.ORDER_CONFIRMATION.value,
                "channel": NotificationChannel.EMAIL.value,
                "subject": "Your order has been confirmed",
                "body": "Dear {{customer_name}},\n\nThank you for your order! Your order ({{order_id}}) has been confirmed and is being processed.\n\nTotal: ${{total_amount}}\n\nYou can check your order status anytime by visiting your account.\n\nThank you for shopping with us!",
                "created_at": datetime.now(),
            },
            {
                "template_id": "payment_confirmation_email",
                "notification_type": NotificationType.PAYMENT_CONFIRMATION.value,
                "channel": NotificationChannel.EMAIL.value,
                "subject": "Payment confirmation",
                "body": "Dear {{customer_name}},\n\nYour payment of ${{amount}} for order {{order_id}} has been successfully processed.\n\nThank you for shopping with us!",
                "created_at": datetime.now(),
            },
            {
                "template_id": "shipping_confirmation_email",
                "notification_type": NotificationType.SHIPPING_CONFIRMATION.value,
                "channel": NotificationChannel.EMAIL.value,
                "subject": "Your order has been shipped",
                "body": "Dear {{customer_name}},\n\nGreat news! Your order ({{order_id}}) has been shipped and is on its way to you.\n\nCarrier: {{carrier}}\nTracking Number: {{tracking_number}}\nEstimated Delivery: {{estimated_delivery_date}}\n\nThank you for shopping with us!",
                "created_at": datetime.now(),
            },
            {
                "template_id": "order_cancelled_email",
                "notification_type": NotificationType.ORDER_CANCELLED.value,
                "channel": NotificationChannel.EMAIL.value,
                "subject": "Your order has been cancelled",
                "body": "Dear {{customer_name}},\n\nWe're sorry to inform you that your order ({{order_id}}) has been cancelled.\n\nReason: {{cancellation_reason}}\n\nIf you have any questions, please contact our customer service.\n\nThank you for your understanding.",
                "created_at": datetime.now(),
            },
        ]

        await self.db[self.templates_collection].insert_many(templates)
        print("Sample notification templates created")

    async def send_notification(
        self, notification_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a notification"""
        # Generate notification ID if not provided
        if "notification_id" not in notification_data:
            notification_data["notification_id"] = str(uuid.uuid4())

        # Set default values if not provided
        notification_data.setdefault("status", NotificationStatus.PENDING.value)
        notification_data.setdefault("created_at", datetime.now())
        notification_data.setdefault("updated_at", datetime.now())

        # Get notification type
        notification_type = notification_data.get("notification_type")

        # Default to order confirmation if not specified
        if not notification_type:
            notification_type = NotificationType.ORDER_CONFIRMATION.value
            notification_data["notification_type"] = notification_type

        # Try to get customer_id from data
        if "customer_id" not in notification_data and "order_data" in notification_data:
            order_data = notification_data.get("order_data", {})
            notification_data["customer_id"] = order_data.get("customer_id")

        # Try to get order_id from data
        if "order_id" not in notification_data and "order_data" in notification_data:
            order_data = notification_data.get("order_data", {})
            notification_data["order_id"] = order_data.get("order_id")

        # Default channels if not provided
        if "channels" not in notification_data:
            notification_data["channels"] = [NotificationChannel.EMAIL.value]

        # Determine template_id if not provided
        if "template_id" not in notification_data:
            channel = (
                notification_data["channels"][0]
                if notification_data["channels"]
                else NotificationChannel.EMAIL.value
            )
            notification_data["template_id"] = f"{notification_type}_{channel}"

        # For demo purposes, simulate notification sending
        success = self._simulate_notification_sending()

        if success:
            notification_data["status"] = NotificationStatus.SENT.value
            notification_data["sent_at"] = datetime.now()
        else:
            notification_data["status"] = NotificationStatus.FAILED.value
            notification_data["error_message"] = "Failed to send notification"

        # Update timestamp
        notification_data["updated_at"] = datetime.now()

        # Record notification in database
        await self.db[self.notifications_collection].insert_one(notification_data)

        print(
            f"Notification processed: {notification_data['notification_id']} - Status: {notification_data['status']}"
        )

        # Unlike other services, we don't fail the saga if notification fails
        # Just log the error and continue
        return notification_data

    def _simulate_notification_sending(self) -> bool:
        """Simulate notification sending with a high success rate"""
        # For demo purposes, succeed 98% of the time
        return random.random() <= 0.98

    async def get_notification(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Get notification by ID"""
        notification = await self.db[self.notifications_collection].find_one(
            {"notification_id": notification_id}
        )
        return notification

    async def cancel_notification(
        self, notification_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cancel a notification if possible"""
        # This is a no-op compensation action, as notifications can't be "unsent"
        # But we'll mark them as cancelled for tracking purposes

        # Get notification ID or order ID
        notification_id = notification_data.get("notification_id")
        order_id = notification_data.get("order_id")

        if not notification_id and not order_id:
            # Try to get from original response
            original_response = notification_data.get("original_response", {})
            notification_id = original_response.get("notification_id")
            order_id = original_response.get("order_id")

        if not notification_id and not order_id:
            return {
                "success": False,
                "message": "notification_id or order_id is required for cancellation",
            }

        # Query for the notification
        query = {}
        if notification_id:
            query["notification_id"] = notification_id
        else:
            query["order_id"] = order_id

        # Only cancel pending notifications
        query["status"] = NotificationStatus.PENDING.value

        # Update to cancelled
        result = await self.db[self.notifications_collection].update_many(
            query,
            {
                "$set": {
                    "status": NotificationStatus.CANCELLED.value,
                    "updated_at": datetime.now(),
                    "cancellation_reason": notification_data.get(
                        "reason", "Order cancelled"
                    ),
                }
            },
        )

        if result.modified_count > 0:
            print(f"Cancelled {result.modified_count} notification(s)")
            return {
                "success": True,
                "message": f"Cancelled {result.modified_count} notification(s)",
                "modified_count": result.modified_count,
            }
        else:
            print("No notifications found to cancel or notifications already sent")
            return {
                "success": True,
                "message": "No notifications found to cancel or notifications already sent",
                "modified_count": 0,
            }

    async def list_notifications(
        self,
        customer_id: Optional[str] = None,
        order_id: Optional[str] = None,
        status: Optional[NotificationStatus] = None,
        notification_type: Optional[NotificationType] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """List notifications with optional filtering"""
        query = {}

        if customer_id:
            query["customer_id"] = customer_id

        if order_id:
            query["order_id"] = order_id

        if status:
            query["status"] = (
                status.value if isinstance(status, NotificationStatus) else status
            )

        if notification_type:
            query["notification_type"] = (
                notification_type.value
                if isinstance(notification_type, NotificationType)
                else notification_type
            )

        cursor = (
            self.db[self.notifications_collection].find(query).skip(skip).limit(limit)
        )
        notifications = await cursor.to_list(length=limit)

        return notifications

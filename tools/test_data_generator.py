#!/usr/bin/env python3
"""
Comprehensive Test Data Generator for E-commerce Saga System

Generates realistic test data for all services based on:
- Functional test scenarios
- Chaos testing requirements
- Data consistency validation needs
- Service API schemas
- Performance testing requirements

Usage:
    python test_data_generator.py --reset
    python test_data_generator.py --customers 100 --products 200 --orders 50
    python test_data_generator.py --cleanup
"""

import asyncio
import argparse
import uuid
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from faker import Faker

# Initialize Faker for realistic data
fake = Faker()


class TestDataGenerator:
    def __init__(self):
        self.client = None
        self.db = None
        self.generated_data = {
            "customers": [],
            "products": [],
            "orders": [],
            "payments": [],
            "shipments": [],
            "notifications": [],
            "inventory_reservations": [],
            "saga_logs": [],
        }

    async def connect(self):
        """Connect to MongoDB"""
        self.client = AsyncIOMotorClient("mongodb://localhost:27017")
        self.db = self.client.ecommerce_saga
        print("🔗 Connected to MongoDB")

    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()

    async def cleanup_all_data(self):
        """Clean up all test data"""
        print("🧹 Cleaning up all test data...")

        collections = [
            "customers",
            "inventory",
            "orders",
            "payments",
            "shipments",
            "notifications",
            "inventory_reservations",
            "saga_logs",
            "notification_templates",
        ]

        for collection in collections:
            result = await self.db[collection].delete_many({})
            print(f"  📂 Deleted {result.deleted_count} documents from {collection}")

    async def generate_customers(self, count: int = 50) -> List[Dict]:
        """Generate realistic customer data for all test scenarios"""
        print(f"👥 Generating {count} customers...")

        customers = []
        for i in range(count):
            customer_id = str(uuid.uuid4())

            # Generate shipping addresses (US-focused for consistency)
            shipping_address = {
                "street": fake.street_address(),
                "city": fake.city(),
                "state": fake.state_abbr(),
                "zip_code": fake.zipcode(),
                "country": "US",
                "address_type": "SHIPPING",
            }

            # Some customers have different billing addresses
            billing_address = shipping_address.copy()
            if random.random() < 0.3:  # 30% have different billing
                billing_address.update(
                    {
                        "street": fake.street_address(),
                        "city": fake.city(),
                        "state": fake.state_abbr(),
                        "zip_code": fake.zipcode(),
                        "address_type": "BILLING",
                    }
                )

            customer = {
                "customer_id": customer_id,
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "email": fake.unique.email(),
                "phone": fake.phone_number(),
                "shipping_address": shipping_address,
                "billing_address": billing_address,
                "customer_type": random.choice(["REGULAR", "PREMIUM", "VIP"]),
                "credit_limit": random.uniform(1000, 10000),
                "registration_date": fake.date_time_between(
                    start_date="-2y", end_date="now"
                ),
                "status": random.choice(
                    ["ACTIVE", "ACTIVE", "ACTIVE", "INACTIVE"]
                ),  # 75% active
                "preferences": {
                    "email_notifications": random.choice([True, False]),
                    "sms_notifications": random.choice([True, False]),
                    "marketing_emails": random.choice([True, False]),
                    "preferred_language": "en",
                },
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
            customers.append(customer)

        # Insert customers
        if customers:
            await self.db.customers.insert_many(customers)
            print(f"  ✅ Created {len(customers)} customers")

        self.generated_data["customers"] = customers
        return customers

    async def generate_products(self, count: int = 100) -> List[Dict]:
        """Generate realistic product inventory for all test scenarios"""
        print(f"📦 Generating {count} products...")

        # Product categories with realistic items
        categories = {
            "Electronics": [
                ("Laptop", 800, 2000, "LAP"),
                ("Smartphone", 300, 1200, "PHN"),
                ("Tablet", 200, 800, "TAB"),
                ("Headphones", 50, 300, "HDP"),
                ("Smart Watch", 150, 500, "SWT"),
                ("Camera", 400, 1500, "CAM"),
                ("Gaming Console", 300, 600, "GCN"),
                ("Monitor", 200, 800, "MON"),
            ],
            "Clothing": [
                ("T-Shirt", 15, 50, "TSH"),
                ("Jeans", 40, 120, "JNS"),
                ("Jacket", 60, 200, "JCK"),
                ("Sneakers", 50, 200, "SNK"),
                ("Dress", 30, 150, "DRS"),
                ("Sweater", 25, 100, "SWT"),
                ("Shorts", 20, 60, "SHT"),
                ("Boots", 80, 250, "BOT"),
            ],
            "Home & Garden": [
                ("Coffee Maker", 50, 300, "CFM"),
                ("Vacuum Cleaner", 100, 500, "VAC"),
                ("Bed Sheets", 25, 100, "BDS"),
                ("Kitchen Knife Set", 40, 200, "KNF"),
                ("Plant Pot", 10, 50, "PLT"),
                ("Lamp", 30, 150, "LMP"),
                ("Pillow", 15, 80, "PIL"),
                ("Curtains", 25, 120, "CUR"),
            ],
            "Books": [
                ("Fiction Novel", 10, 25, "FIC"),
                ("Technical Manual", 30, 100, "TEC"),
                ("Cookbook", 20, 50, "COK"),
                ("Biography", 15, 35, "BIO"),
                ("Science Book", 25, 80, "SCI"),
                ("Art Book", 35, 120, "ART"),
                ("Children's Book", 8, 25, "CHI"),
                ("Reference Guide", 40, 150, "REF"),
            ],
            "Sports": [
                ("Running Shoes", 60, 200, "RUN"),
                ("Yoga Mat", 20, 80, "YOG"),
                ("Bicycle", 200, 1000, "BIC"),
                ("Tennis Racket", 50, 300, "TEN"),
                ("Basketball", 25, 60, "BAS"),
                ("Swimming Goggles", 15, 50, "SWM"),
                ("Dumbbells", 30, 150, "DUM"),
                ("Fitness Tracker", 80, 300, "FIT"),
            ],
        }

        products = []
        for i in range(count):
            # Select random category and product
            category = random.choice(list(categories.keys()))
            product_info = random.choice(categories[category])
            name, min_price, max_price, sku_prefix = product_info

            product_id = str(uuid.uuid4())

            # Generate realistic quantities
            base_quantity = random.randint(10, 500)

            # Some products have low stock for testing edge cases
            if random.random() < 0.05:  # 5% low stock
                quantity = random.randint(1, 5)
            elif random.random() < 0.02:  # 2% out of stock
                quantity = 0
            else:
                quantity = base_quantity

            # Reserved quantities (some products have reservations)
            max_reserved = min(quantity, 10)
            reserved_quantity = random.randint(0, max_reserved) if quantity > 0 else 0

            # Product status
            if quantity == 0:
                status = random.choice(["OUT_OF_STOCK", "DISCONTINUED"])
            elif quantity <= 5:
                status = "AVAILABLE"  # Low stock but available
            else:
                status = "AVAILABLE"

            product = {
                "product_id": product_id,
                "name": f"{name} - {fake.color_name()} {fake.word().title()}",
                "description": fake.text(max_nb_chars=200),
                "sku": f"{sku_prefix}-{random.randint(1000, 9999)}",
                "quantity": quantity,
                "reserved_quantity": reserved_quantity,
                "status": status,
                "price": round(random.uniform(min_price, max_price), 2),
                "category": category,
                "brand": fake.company(),
                "weight": round(random.uniform(0.1, 20.0), 2),  # kg
                "dimensions": {
                    "length": round(random.uniform(5, 50), 1),  # cm
                    "width": round(random.uniform(5, 50), 1),
                    "height": round(random.uniform(2, 30), 1),
                },
                "metadata": {
                    "supplier": fake.company(),
                    "warehouse_location": f"WH-{random.randint(1, 10)}",
                    "reorder_level": random.randint(5, 20),
                    "tags": [fake.word() for _ in range(random.randint(1, 3))],
                },
                "created_at": fake.date_time_between(start_date="-1y", end_date="now"),
                "updated_at": datetime.now(),
            }
            products.append(product)

        # Insert products
        if products:
            await self.db.inventory.insert_many(products)
            print(f"  ✅ Created {len(products)} products in inventory")

        self.generated_data["products"] = products
        return products

    async def generate_orders_and_related_data(self, order_count: int = 30):
        """Generate orders and all related data (payments, shipments, notifications, saga logs)"""
        print(f"🛒 Generating {order_count} orders with related data...")

        customers = self.generated_data.get(
            "customers"
        ) or await self.db.customers.find().to_list(None)
        products = self.generated_data.get("products") or await self.db.inventory.find(
            {"quantity": {"$gt": 0}}
        ).to_list(None)

        # Filter products to only include those with available quantity > 0
        available_products = [p for p in products if p.get("quantity", 0) > 0]

        if not customers or not available_products:
            raise ValueError(
                "❌ No customers or available products found. Generate customers and products first."
            )

        orders = []
        payments = []
        shipments = []
        notifications = []
        inventory_reservations = []
        saga_logs = []

        # Order statuses with realistic distribution
        order_statuses = [
            ("COMPLETED", 0.60),  # 60% completed successfully
            ("PENDING", 0.15),  # 15% still processing
            ("CANCELLED", 0.10),  # 10% cancelled
            ("SHIPPED", 0.08),  # 8% shipped
            ("DELIVERED", 0.05),  # 5% delivered
            ("FAILED", 0.02),  # 2% failed
        ]

        for i in range(order_count):
            customer = random.choice(customers)
            order_id = str(uuid.uuid4())
            correlation_id = str(uuid.uuid4())

            # Select 1-4 items for the order
            num_items = random.randint(1, 4)
            selected_products = random.sample(
                available_products, min(num_items, len(available_products))
            )

            order_items = []
            total_amount = 0

            for product in selected_products:
                # Ensure we don't order more than available and at least 1
                max_quantity = min(3, product["quantity"])
                if max_quantity < 1:
                    continue  # Skip products with no available quantity
                quantity = random.randint(1, max_quantity)
                price = product["price"]
                item_total = quantity * price
                total_amount += item_total

                order_items.append(
                    {
                        "product_id": product["product_id"],
                        "name": product["name"],
                        "sku": product["sku"],
                        "quantity": quantity,
                        "unit_price": price,
                        "total_price": round(item_total, 2),
                    }
                )

            # Determine order status with weighted random
            status_weights = [weight for _, weight in order_statuses]
            selected_status = random.choices(
                [status for status, _ in order_statuses], weights=status_weights
            )[0]

            # Generate order date (last 30 days)
            order_date = fake.date_time_between(start_date="-30d", end_date="now")

            # Create order
            order = {
                "order_id": order_id,
                "customer_id": customer["customer_id"],
                "items": order_items,
                "total_amount": round(total_amount, 2),
                "currency": "USD",
                "status": selected_status,
                "shipping_address": customer["shipping_address"],
                "billing_address": customer["billing_address"],
                "payment_method": random.choice(
                    ["CREDIT_CARD", "DEBIT_CARD", "PAYPAL", "BANK_TRANSFER"]
                ),
                "shipping_method": random.choice(
                    ["STANDARD", "EXPRESS", "OVERNIGHT", "PICKUP"]
                ),
                "order_date": order_date,
                "created_at": order_date,
                "updated_at": datetime.now(),
                "metadata": {
                    "channel": random.choice(["WEB", "MOBILE", "API"]),
                    "source": random.choice(["DIRECT", "REFERRAL", "CAMPAIGN"]),
                    "correlation_id": correlation_id,
                },
            }
            orders.append(order)

            # Generate payment data
            payment_status = self._get_payment_status_for_order(selected_status)
            payment = {
                "payment_id": str(uuid.uuid4()),
                "order_id": order_id,
                "customer_id": customer["customer_id"],
                "amount": total_amount,
                "currency": "USD",
                "payment_method": order["payment_method"],
                "status": payment_status,
                "transaction_reference": f"TXN-{random.randint(100000, 999999)}",
                "payment_details": {
                    "card_last_four": (
                        f"****{random.randint(1000, 9999)}"
                        if "CARD" in order["payment_method"]
                        else None
                    ),
                    "provider": random.choice(["Stripe", "PayPal", "Square"]),
                    "fee": round(total_amount * 0.029, 2),  # 2.9% processing fee
                },
                "created_at": order_date + timedelta(minutes=random.randint(1, 5)),
                "updated_at": datetime.now(),
            }
            if payment_status == "COMPLETED":
                payment["completed_at"] = payment["created_at"] + timedelta(
                    seconds=random.randint(30, 300)
                )
            payments.append(payment)

            # Generate shipping data (if order is shipped/delivered)
            if selected_status in ["SHIPPED", "DELIVERED", "COMPLETED"]:
                shipping_status = self._get_shipping_status_for_order(selected_status)
                shipment = {
                    "shipping_id": str(uuid.uuid4()),
                    "order_id": order_id,
                    "customer_id": customer["customer_id"],
                    "address": customer["shipping_address"],
                    "items": order_items,
                    "method": order["shipping_method"],
                    "status": shipping_status,
                    "tracking_number": f"1Z{random.randint(100000000000000, 999999999999999)}",
                    "carrier": random.choice(["UPS", "FedEx", "USPS", "DHL"]),
                    "estimated_delivery_date": order_date
                    + timedelta(days=random.randint(2, 7)),
                    "created_at": order_date + timedelta(hours=random.randint(1, 24)),
                    "updated_at": datetime.now(),
                }
                if shipping_status == "DELIVERED":
                    shipment["delivered_at"] = shipment["created_at"] + timedelta(
                        days=random.randint(1, 5)
                    )
                shipments.append(shipment)

            # Generate notifications
            notification_types = ["ORDER_CONFIRMATION"]
            if payment_status == "COMPLETED":
                notification_types.append("PAYMENT_CONFIRMATION")
            if selected_status in ["SHIPPED", "DELIVERED"]:
                notification_types.append("SHIPPING_CONFIRMATION")
            if selected_status == "CANCELLED":
                notification_types.append("ORDER_CANCELLED")

            for notif_type in notification_types:
                notification = {
                    "notification_id": str(uuid.uuid4()),
                    "notification_type": notif_type,
                    "customer_id": customer["customer_id"],
                    "order_id": order_id,
                    "channels": ["EMAIL"],
                    "status": random.choice(
                        ["SENT", "SENT", "DELIVERED", "FAILED"]
                    ),  # Mostly sent
                    "data": {
                        "customer_name": f"{customer['first_name']} {customer['last_name']}",
                        "order_id": order_id,
                        "total_amount": total_amount,
                    },
                    "created_at": order_date + timedelta(minutes=random.randint(5, 30)),
                    "updated_at": datetime.now(),
                }
                if notification["status"] in ["SENT", "DELIVERED"]:
                    notification["sent_at"] = notification["created_at"] + timedelta(
                        seconds=random.randint(10, 60)
                    )
                notifications.append(notification)

            # Generate inventory reservations (for non-cancelled orders)
            if selected_status != "CANCELLED":
                for item in order_items:
                    reservation = {
                        "reservation_id": str(uuid.uuid4()),
                        "product_id": item["product_id"],
                        "order_id": order_id,
                        "customer_id": customer["customer_id"],
                        "quantity": item["quantity"],
                        "status": (
                            "RESERVED"
                            if selected_status in ["PENDING", "PROCESSING"]
                            else "CONSUMED"
                        ),
                        "created_at": order_date + timedelta(minutes=1),
                        "metadata": {"correlation_id": correlation_id},
                    }
                    inventory_reservations.append(reservation)

            # Generate saga logs
            saga_log = self._generate_saga_log(
                order_id, correlation_id, selected_status, order_date
            )
            saga_logs.append(saga_log)

        # Insert all data
        if orders:
            await self.db.orders.insert_many(orders)
            print(f"  ✅ Created {len(orders)} orders")

        if payments:
            await self.db.payments.insert_many(payments)
            print(f"  ✅ Created {len(payments)} payments")

        if shipments:
            await self.db.shipments.insert_many(shipments)
            print(f"  ✅ Created {len(shipments)} shipments")

        if notifications:
            await self.db.notifications.insert_many(notifications)
            print(f"  ✅ Created {len(notifications)} notifications")

        if inventory_reservations:
            await self.db.inventory_reservations.insert_many(inventory_reservations)
            print(f"  ✅ Created {len(inventory_reservations)} inventory reservations")

        if saga_logs:
            await self.db.saga_logs.insert_many(saga_logs)
            print(f"  ✅ Created {len(saga_logs)} saga logs")

        # Store in generated data
        self.generated_data.update(
            {
                "orders": orders,
                "payments": payments,
                "shipments": shipments,
                "notifications": notifications,
                "inventory_reservations": inventory_reservations,
                "saga_logs": saga_logs,
            }
        )

    def _get_payment_status_for_order(self, order_status: str) -> str:
        """Get appropriate payment status based on order status"""
        status_mapping = {
            "COMPLETED": "COMPLETED",
            "SHIPPED": "COMPLETED",
            "DELIVERED": "COMPLETED",
            "PENDING": random.choice(["PENDING", "PROCESSING"]),
            "CANCELLED": random.choice(["FAILED", "REFUNDED"]),
            "FAILED": "FAILED",
        }
        return status_mapping.get(order_status, "PENDING")

    def _get_shipping_status_for_order(self, order_status: str) -> str:
        """Get appropriate shipping status based on order status"""
        status_mapping = {
            "COMPLETED": random.choice(["DELIVERED", "IN_TRANSIT"]),
            "SHIPPED": random.choice(["IN_TRANSIT", "PICKED_UP"]),
            "DELIVERED": "DELIVERED",
        }
        return status_mapping.get(order_status, "PENDING")

    def _generate_saga_log(
        self,
        order_id: str,
        correlation_id: str,
        order_status: str,
        order_date: datetime,
    ) -> Dict:
        """Generate realistic saga log based on order status"""
        saga_id = str(uuid.uuid4())

        # Define saga steps
        steps = [
            {"service": "order", "action": "create_order", "status": "COMPLETED"},
            {
                "service": "inventory",
                "action": "reserve_inventory",
                "status": "COMPLETED",
            },
            {"service": "payment", "action": "process_payment", "status": "COMPLETED"},
            {
                "service": "shipping",
                "action": "schedule_shipping",
                "status": "COMPLETED",
            },
            {
                "service": "notification",
                "action": "send_confirmation",
                "status": "COMPLETED",
            },
        ]

        # Modify steps based on order status
        if order_status == "CANCELLED":
            saga_status = "COMPENSATED"
            # Some steps succeeded, then compensation was triggered
            compensation_point = random.randint(1, 4)
            for i, step in enumerate(steps):
                if i <= compensation_point:
                    step["status"] = "COMPLETED"
                else:
                    step["status"] = "COMPENSATED"
        elif order_status == "FAILED":
            saga_status = "FAILED"
            failure_point = random.randint(1, 4)
            for i, step in enumerate(steps):
                if i < failure_point:
                    step["status"] = "COMPLETED"
                elif i == failure_point:
                    step["status"] = "FAILED"
                else:
                    step["status"] = "NOT_EXECUTED"
        elif order_status == "PENDING":
            saga_status = "IN_PROGRESS"
            progress_point = random.randint(0, 3)
            for i, step in enumerate(steps):
                if i <= progress_point:
                    step["status"] = "COMPLETED"
                else:
                    step["status"] = "PENDING"
        else:
            saga_status = "COMPLETED"

        # Calculate timing
        start_time = order_date
        duration_ms = random.randint(1000, 30000)  # 1-30 seconds
        end_time = start_time + timedelta(milliseconds=duration_ms)

        saga_log = {
            "saga_id": saga_id,
            "correlation_id": correlation_id,
            "order_id": order_id,
            "saga_type": "ORDER_PROCESSING",
            "status": saga_status,
            "steps": steps,
            "total_duration_ms": duration_ms,
            "started_at": start_time,
            "completed_at": end_time if saga_status != "IN_PROGRESS" else None,
            "created_at": start_time,
            "updated_at": datetime.now(),
            "metadata": {
                "retries": random.randint(0, 2),
                "error_count": 1 if saga_status == "FAILED" else 0,
            },
        }

        return saga_log

    async def generate_notification_templates(self):
        """Generate notification templates for the system"""
        print("📧 Generating notification templates...")

        templates = [
            {
                "template_id": "order_confirmation_email",
                "notification_type": "ORDER_CONFIRMATION",
                "channel": "EMAIL",
                "subject": "Your order has been confirmed - Order {{order_id}}",
                "body": """
Dear {{customer_name}},

Thank you for your order! Your order ({{order_id}}) has been confirmed and is being processed.

Order Details:
- Order ID: {{order_id}}
- Total Amount: ${{total_amount}}
- Order Date: {{order_date}}

You can track your order status anytime by visiting your account.

Thank you for shopping with us!

Best regards,
E-commerce Team
                """.strip(),
                "created_at": datetime.now(),
            },
            {
                "template_id": "payment_confirmation_email",
                "notification_type": "PAYMENT_CONFIRMATION",
                "channel": "EMAIL",
                "subject": "Payment confirmation - Order {{order_id}}",
                "body": """
Dear {{customer_name}},

Your payment of ${{amount}} for order {{order_id}} has been successfully processed.

Payment Details:
- Amount: ${{amount}}
- Payment Method: {{payment_method}}
- Transaction Reference: {{transaction_reference}}

Thank you for shopping with us!

Best regards,
E-commerce Team
                """.strip(),
                "created_at": datetime.now(),
            },
            {
                "template_id": "shipping_confirmation_email",
                "notification_type": "SHIPPING_CONFIRMATION",
                "channel": "EMAIL",
                "subject": "Your order has been shipped - Order {{order_id}}",
                "body": """
Dear {{customer_name}},

Great news! Your order ({{order_id}}) has been shipped and is on its way to you.

Shipping Details:
- Carrier: {{carrier}}
- Tracking Number: {{tracking_number}}
- Estimated Delivery: {{estimated_delivery_date}}

You can track your package using the tracking number above.

Thank you for shopping with us!

Best regards,
E-commerce Team
                """.strip(),
                "created_at": datetime.now(),
            },
            {
                "template_id": "order_cancelled_email",
                "notification_type": "ORDER_CANCELLED",
                "channel": "EMAIL",
                "subject": "Order cancelled - Order {{order_id}}",
                "body": """
Dear {{customer_name}},

We're sorry to inform you that your order ({{order_id}}) has been cancelled.

{{#cancellation_reason}}
Reason: {{cancellation_reason}}
{{/cancellation_reason}}

If any payment was processed, it will be refunded within 3-5 business days.

If you have any questions, please contact our customer service.

Best regards,
E-commerce Team
                """.strip(),
                "created_at": datetime.now(),
            },
        ]

        await self.db.notification_templates.insert_many(templates)
        print(f"  ✅ Created {len(templates)} notification templates")

    async def print_data_summary(self):
        """Print summary of generated data"""
        print("\n📊 Generated Data Summary")
        print("=" * 50)

        collections = {
            "customers": "👥 Customers",
            "inventory": "📦 Products",
            "orders": "🛒 Orders",
            "payments": "💳 Payments",
            "shipments": "🚛 Shipments",
            "notifications": "📧 Notifications",
            "inventory_reservations": "📋 Reservations",
            "saga_logs": "📝 Saga Logs",
            "notification_templates": "📄 Templates",
        }

        for collection, label in collections.items():
            count = await self.db[collection].count_documents({})
            print(f"{label:20} {count:6} records")

        # Additional statistics
        print("\n📈 Statistics")
        print("-" * 30)

        # Order status distribution
        order_stats = await self.db.orders.aggregate(
            [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
        ).to_list(None)

        if order_stats:
            print("Order Status Distribution:")
            for stat in order_stats:
                print(f"  {stat['_id']:12} {stat['count']:6} orders")

        # Top product categories
        category_stats = await self.db.inventory.aggregate(
            [
                {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5},
            ]
        ).to_list(None)

        if category_stats:
            print("\nTop Product Categories:")
            for stat in category_stats:
                print(f"  {stat['_id']:15} {stat['count']:6} products")

        print("\n✅ Test data generation complete!")
        print("\n🚀 Next steps:")
        print("  - Run 'make health' to check service health")
        print("  - Run 'make test-func' to run functional tests")
        print("  - Run 'make monitor' to start monitoring dashboard")


async def main():
    parser = argparse.ArgumentParser(
        description="Generate comprehensive test data for e-commerce saga system"
    )

    parser.add_argument(
        "--customers", type=int, default=50, help="Number of customers to generate"
    )
    parser.add_argument(
        "--products", type=int, default=100, help="Number of products to generate"
    )
    parser.add_argument(
        "--orders", type=int, default=30, help="Number of orders to generate"
    )
    parser.add_argument(
        "--reset", action="store_true", help="Clean all data and generate fresh data"
    )
    parser.add_argument("--cleanup", action="store_true", help="Clean up all test data")

    args = parser.parse_args()

    generator = TestDataGenerator()

    try:
        await generator.connect()

        if args.cleanup:
            await generator.cleanup_all_data()
            print("✅ Data cleanup complete")
            return

        if args.reset:
            await generator.cleanup_all_data()

        # Generate data in correct order
        print("🚀 Starting comprehensive test data generation...")
        print(
            f"📊 Targets: {args.customers} customers, {args.products} products, {args.orders} orders"
        )

        # Only generate if counts > 0
        if args.customers > 0:
            await generator.generate_customers(args.customers)

        if args.products > 0:
            await generator.generate_products(args.products)

        if args.orders > 0:
            await generator.generate_orders_and_related_data(args.orders)

        await generator.generate_notification_templates()
        await generator.print_data_summary()

    except Exception as e:
        print(f"❌ Data generation failed: {str(e)}")
        sys.exit(1)
    finally:
        await generator.close()


if __name__ == "__main__":
    asyncio.run(main())

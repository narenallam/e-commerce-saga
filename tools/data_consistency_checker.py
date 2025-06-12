#!/usr/bin/env python3
"""
Data Consistency Checker for E-commerce Saga System

Verifies data consistency across all services and identifies
potential data integrity issues.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient


class ConsistencyIssue:
    def __init__(
        self, issue_type: str, severity: str, description: str, details: Dict = None
    ):
        self.issue_type = issue_type
        self.severity = severity  # critical, warning, info
        self.description = description
        self.details = details or {}
        self.timestamp = datetime.now()


class DataConsistencyChecker:
    def __init__(self):
        self.client = None
        self.db = None
        self.issues: List[ConsistencyIssue] = []

    async def connect(self):
        """Connect to MongoDB"""
        self.client = AsyncIOMotorClient("mongodb://localhost:27017")
        self.db = self.client.ecommerce_saga
        print("Connected to MongoDB for consistency checking")

    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()

    def add_issue(self, issue: ConsistencyIssue):
        """Add consistency issue"""
        self.issues.append(issue)
        severity_emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}
        emoji = severity_emoji.get(issue.severity, "❓")
        print(f"{emoji} {issue.issue_type}: {issue.description}")

    async def check_order_payment_consistency(self):
        """Check orders have corresponding payments"""
        print("\n🔍 Checking Order-Payment Consistency...")

        # Find completed orders without payments
        completed_orders = await self.db.orders.find({"status": "COMPLETED"}).to_list(
            None
        )

        for order in completed_orders:
            payment = await self.db.payments.find_one({"order_id": order["order_id"]})

            if not payment:
                self.add_issue(
                    ConsistencyIssue(
                        "MISSING_PAYMENT",
                        "critical",
                        f"Completed order {order['order_id']} has no payment record",
                        {
                            "order_id": order["order_id"],
                            "customer_id": order["customer_id"],
                        },
                    )
                )
            elif payment.get("status") != "COMPLETED":
                self.add_issue(
                    ConsistencyIssue(
                        "PAYMENT_STATUS_MISMATCH",
                        "critical",
                        f"Order {order['order_id']} is completed but payment status is {payment.get('status')}",
                        {
                            "order_id": order["order_id"],
                            "payment_status": payment.get("status"),
                        },
                    )
                )

    async def check_order_shipping_consistency(self):
        """Check orders have corresponding shipments"""
        print("\n🔍 Checking Order-Shipping Consistency...")

        # Find shipped/delivered orders without shipments
        shipped_orders = await self.db.orders.find(
            {"status": {"$in": ["SHIPPED", "DELIVERED"]}}
        ).to_list(None)

        for order in shipped_orders:
            shipment = await self.db.shipments.find_one({"order_id": order["order_id"]})

            if not shipment:
                self.add_issue(
                    ConsistencyIssue(
                        "MISSING_SHIPMENT",
                        "critical",
                        f"Shipped order {order['order_id']} has no shipment record",
                        {"order_id": order["order_id"]},
                    )
                )
            elif (
                order["status"] == "DELIVERED" and shipment.get("status") != "DELIVERED"
            ):
                self.add_issue(
                    ConsistencyIssue(
                        "SHIPMENT_STATUS_MISMATCH",
                        "warning",
                        f"Order {order['order_id']} is delivered but shipment status is {shipment.get('status')}",
                        {
                            "order_id": order["order_id"],
                            "shipment_status": shipment.get("status"),
                        },
                    )
                )

    async def check_inventory_consistency(self):
        """Check inventory and reservation consistency"""
        print("\n🔍 Checking Inventory Consistency...")

        # Check for negative inventory
        negative_inventory = await self.db.inventory.find(
            {"quantity": {"$lt": 0}}
        ).to_list(None)

        for item in negative_inventory:
            self.add_issue(
                ConsistencyIssue(
                    "NEGATIVE_INVENTORY",
                    "critical",
                    f"Product {item['product_id']} has negative quantity: {item['quantity']}",
                    {"product_id": item["product_id"], "quantity": item["quantity"]},
                )
            )

        # Check for excessive reserved quantities
        products = await self.db.inventory.find({}).to_list(None)

        for product in products:
            if product["reserved_quantity"] > product["quantity"]:
                self.add_issue(
                    ConsistencyIssue(
                        "EXCESSIVE_RESERVATION",
                        "critical",
                        f"Product {product['product_id']} has more reserved ({product['reserved_quantity']}) than available ({product['quantity']})",
                        {
                            "product_id": product["product_id"],
                            "quantity": product["quantity"],
                            "reserved": product["reserved_quantity"],
                        },
                    )
                )

        # Check for old unreleased reservations
        cutoff_time = datetime.now() - timedelta(hours=2)
        old_reservations = await self.db.inventory_reservations.find(
            {"created_at": {"$lt": cutoff_time}, "status": "RESERVED"}
        ).to_list(None)

        for reservation in old_reservations:
            # Check if order was cancelled but reservation not released
            order = await self.db.orders.find_one({"order_id": reservation["order_id"]})

            if order and order.get("status") == "CANCELLED":
                self.add_issue(
                    ConsistencyIssue(
                        "UNRELEASED_RESERVATION",
                        "warning",
                        f"Reservation {reservation['reservation_id']} not released for cancelled order",
                        {
                            "reservation_id": reservation["reservation_id"],
                            "order_id": reservation["order_id"],
                            "age_hours": (
                                datetime.now() - reservation["created_at"]
                            ).total_seconds()
                            / 3600,
                        },
                    )
                )

    async def check_saga_consistency(self):
        """Check saga logs consistency"""
        print("\n🔍 Checking Saga Consistency...")

        # Check for long-running sagas
        cutoff_time = datetime.now() - timedelta(hours=1)
        long_running_sagas = await self.db.saga_logs.find(
            {"status": "IN_PROGRESS", "created_at": {"$lt": cutoff_time}}
        ).to_list(None)

        for saga in long_running_sagas:
            age_hours = (datetime.now() - saga["created_at"]).total_seconds() / 3600
            self.add_issue(
                ConsistencyIssue(
                    "LONG_RUNNING_SAGA",
                    "warning",
                    f"Saga {saga['saga_id']} has been running for {age_hours:.1f} hours",
                    {"saga_id": saga["saga_id"], "age_hours": age_hours},
                )
            )

        # Check for sagas without corresponding orders
        sagas = await self.db.saga_logs.find({}).to_list(None)

        for saga in sagas:
            order_id = saga.get("order_id")
            if order_id:
                order = await self.db.orders.find_one({"order_id": order_id})
                if not order:
                    self.add_issue(
                        ConsistencyIssue(
                            "ORPHANED_SAGA",
                            "warning",
                            f"Saga {saga['saga_id']} references non-existent order {order_id}",
                            {"saga_id": saga["saga_id"], "order_id": order_id},
                        )
                    )

    async def check_payment_refund_consistency(self):
        """Check payment and refund consistency"""
        print("\n🔍 Checking Payment-Refund Consistency...")

        # Check refunds have corresponding payments
        refunds = await self.db.refunds.find({}).to_list(None)

        for refund in refunds:
            payment = await self.db.payments.find_one(
                {"payment_id": refund["payment_id"]}
            )

            if not payment:
                self.add_issue(
                    ConsistencyIssue(
                        "ORPHANED_REFUND",
                        "critical",
                        f"Refund {refund['refund_id']} references non-existent payment {refund['payment_id']}",
                        {
                            "refund_id": refund["refund_id"],
                            "payment_id": refund["payment_id"],
                        },
                    )
                )
            elif refund["amount"] > payment["amount"]:
                self.add_issue(
                    ConsistencyIssue(
                        "EXCESSIVE_REFUND",
                        "critical",
                        f"Refund {refund['refund_id']} amount (${refund['amount']}) exceeds payment amount (${payment['amount']})",
                        {
                            "refund_id": refund["refund_id"],
                            "refund_amount": refund["amount"],
                            "payment_amount": payment["amount"],
                        },
                    )
                )

    async def check_notification_consistency(self):
        """Check notification consistency"""
        print("\n🔍 Checking Notification Consistency...")

        # Check for orders without confirmation notifications
        recent_orders = await self.db.orders.find(
            {
                "created_at": {"$gte": datetime.now() - timedelta(hours=24)},
                "status": {"$ne": "CANCELLED"},
            }
        ).to_list(None)

        for order in recent_orders:
            confirmation = await self.db.notifications.find_one(
                {
                    "order_id": order["order_id"],
                    "notification_type": "ORDER_CONFIRMATION",
                }
            )

            if not confirmation:
                self.add_issue(
                    ConsistencyIssue(
                        "MISSING_ORDER_CONFIRMATION",
                        "warning",
                        f"Order {order['order_id']} has no confirmation notification",
                        {
                            "order_id": order["order_id"],
                            "customer_id": order["customer_id"],
                        },
                    )
                )

    async def check_amount_consistency(self):
        """Check amount consistency across services"""
        print("\n🔍 Checking Amount Consistency...")

        # Check order vs payment amounts
        orders = await self.db.orders.find({"status": "COMPLETED"}).to_list(None)

        for order in orders:
            payment = await self.db.payments.find_one({"order_id": order["order_id"]})

            if payment and abs(order["total_amount"] - payment["amount"]) > 0.01:
                self.add_issue(
                    ConsistencyIssue(
                        "AMOUNT_MISMATCH",
                        "critical",
                        f"Order {order['order_id']} amount (${order['total_amount']}) doesn't match payment amount (${payment['amount']})",
                        {
                            "order_id": order["order_id"],
                            "order_amount": order["total_amount"],
                            "payment_amount": payment["amount"],
                        },
                    )
                )

    async def run_all_checks(self):
        """Run all consistency checks"""
        print("🔍 Starting Data Consistency Checks...")
        print("=" * 60)

        checks = [
            self.check_order_payment_consistency,
            self.check_order_shipping_consistency,
            self.check_inventory_consistency,
            self.check_saga_consistency,
            self.check_payment_refund_consistency,
            self.check_notification_consistency,
            self.check_amount_consistency,
        ]

        for check in checks:
            try:
                await check()
            except Exception as e:
                self.add_issue(
                    ConsistencyIssue(
                        "CHECK_ERROR",
                        "critical",
                        f"Error running {check.__name__}: {str(e)}",
                        {"check": check.__name__},
                    )
                )

        self.print_summary()

    def print_summary(self):
        """Print consistency check summary"""
        print("\n" + "=" * 60)
        print("📋 DATA CONSISTENCY SUMMARY")
        print("=" * 60)

        critical_issues = [i for i in self.issues if i.severity == "critical"]
        warning_issues = [i for i in self.issues if i.severity == "warning"]
        info_issues = [i for i in self.issues if i.severity == "info"]

        print(f"Total Issues Found: {len(self.issues)}")
        print(f"  Critical: {len(critical_issues)} 🚨")
        print(f"  Warning:  {len(warning_issues)} ⚠️")
        print(f"  Info:     {len(info_issues)} ℹ️")

        if critical_issues:
            print(f"\n🚨 CRITICAL ISSUES ({len(critical_issues)}):")
            for issue in critical_issues:
                print(f"  • {issue.description}")

        if warning_issues:
            print(f"\n⚠️  WARNING ISSUES ({len(warning_issues)}):")
            for issue in warning_issues:
                print(f"  • {issue.description}")

        if len(self.issues) == 0:
            print("\n✅ No consistency issues found!")
        else:
            print(f"\n📊 Issue Types:")
            issue_types = {}
            for issue in self.issues:
                issue_types[issue.issue_type] = issue_types.get(issue.issue_type, 0) + 1

            for issue_type, count in sorted(issue_types.items()):
                print(f"  {issue_type}: {count}")

        print("=" * 60)


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Check data consistency across e-commerce saga system"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to fix simple issues (not implemented)",
    )

    args = parser.parse_args()

    checker = DataConsistencyChecker()

    try:
        await checker.connect()
        await checker.run_all_checks()

        # Exit with error code if critical issues found
        critical_count = len([i for i in checker.issues if i.severity == "critical"])
        if critical_count > 0:
            print(f"\n❌ Found {critical_count} critical issues")
            sys.exit(1)
        else:
            print("\n✅ No critical issues found")

    except Exception as e:
        print(f"❌ Consistency check failed: {str(e)}")
        sys.exit(1)
    finally:
        await checker.close()


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Log Analysis Tool for E-commerce Saga System

Provides insights into system behavior, performance, and errors
from centralized logs and database records.
"""

import asyncio
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient


class LogAnalyzer:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        """Connect to MongoDB"""
        self.client = AsyncIOMotorClient("mongodb://localhost:27017")
        self.db = self.client.ecommerce_saga
        print("Connected to MongoDB for log analysis")

    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()

    async def analyze_saga_performance(self, hours: int = 24):
        """Analyze saga performance over specified hours"""
        print(f"\n📊 Saga Performance Analysis (Last {hours} hours)")
        print("=" * 60)

        cutoff_time = datetime.now() - timedelta(hours=hours)

        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff_time}}},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "avg_duration": {"$avg": "$total_duration_ms"},
                    "max_duration": {"$max": "$total_duration_ms"},
                    "min_duration": {"$min": "$total_duration_ms"},
                }
            },
            {"$sort": {"count": -1}},
        ]

        results = await self.db.saga_logs.aggregate(pipeline).to_list(None)

        total_sagas = sum(result["count"] for result in results)

        for result in results:
            status = result["_id"]
            count = result["count"]
            percentage = (count / total_sagas * 100) if total_sagas > 0 else 0
            avg_duration = result.get("avg_duration", 0) or 0
            max_duration = result.get("max_duration", 0) or 0
            min_duration = result.get("min_duration", 0) or 0

            print(
                f"{status:12} {count:6} ({percentage:5.1f}%) | "
                f"Avg: {avg_duration:6.0f}ms | "
                f"Max: {max_duration:6.0f}ms | "
                f"Min: {min_duration:6.0f}ms"
            )

        print(f"{'Total':12} {total_sagas:6}")

    async def analyze_service_errors(self, hours: int = 24):
        """Analyze errors by service"""
        print(f"\n🚨 Service Error Analysis (Last {hours} hours)")
        print("=" * 60)

        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Analyze saga step failures
        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff_time}}},
            {"$unwind": "$steps"},
            {"$match": {"steps.status": "FAILED"}},
            {
                "$group": {
                    "_id": "$steps.service",
                    "error_count": {"$sum": 1},
                    "errors": {"$push": "$steps.error_message"},
                }
            },
            {"$sort": {"error_count": -1}},
        ]

        results = await self.db.saga_logs.aggregate(pipeline).to_list(None)

        if not results:
            print("No service errors found ✅")
            return

        for result in results:
            service = result["_id"]
            error_count = result["error_count"]
            print(f"{service:15} {error_count:4} errors")

            # Show unique error messages
            unique_errors = list(set(filter(None, result["errors"])))
            for error in unique_errors[:3]:  # Show top 3 unique errors
                print(f"  • {error[:80]}...")

    async def analyze_order_patterns(self, hours: int = 24):
        """Analyze order patterns"""
        print(f"\n📦 Order Pattern Analysis (Last {hours} hours)")
        print("=" * 60)

        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Orders by status
        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff_time}}},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "avg_amount": {"$avg": "$total_amount"},
                    "total_amount": {"$sum": "$total_amount"},
                }
            },
            {"$sort": {"count": -1}},
        ]

        results = await self.db.orders.aggregate(pipeline).to_list(None)

        total_orders = sum(result["count"] for result in results)
        total_revenue = sum(result["total_amount"] for result in results)

        print("Order Status Distribution:")
        for result in results:
            status = result["_id"]
            count = result["count"]
            percentage = (count / total_orders * 100) if total_orders > 0 else 0
            avg_amount = result.get("avg_amount", 0) or 0
            total_amount = result.get("total_amount", 0) or 0

            print(
                f"{status:12} {count:6} ({percentage:5.1f}%) | "
                f"Avg: ${avg_amount:7.2f} | "
                f"Total: ${total_amount:10.2f}"
            )

        print(
            f"{'TOTAL':12} {total_orders:6} orders | "
            f"Revenue: ${total_revenue:10.2f}"
        )

    async def analyze_performance_trends(self, hours: int = 24):
        """Analyze performance trends"""
        print(f"\n⚡ Performance Trend Analysis (Last {hours} hours)")
        print("=" * 60)

        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Hourly performance
        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff_time}, "status": "COMPLETED"}},
            {"$project": {"hour": {"$hour": "$created_at"}, "total_duration_ms": 1}},
            {
                "$group": {
                    "_id": "$hour",
                    "count": {"$sum": 1},
                    "avg_duration": {"$avg": "$total_duration_ms"},
                    "max_duration": {"$max": "$total_duration_ms"},
                }
            },
            {"$sort": {"_id": 1}},
        ]

        results = await self.db.saga_logs.aggregate(pipeline).to_list(None)

        if not results:
            print("No completed sagas found for trend analysis")
            return

        print("Hourly Performance (Completed Sagas):")
        print("Hour   Count   Avg Duration   Max Duration")
        print("-" * 45)

        for result in results:
            hour = result["_id"]
            count = result["count"]
            avg_duration = result.get("avg_duration", 0) or 0
            max_duration = result.get("max_duration", 0) or 0

            print(
                f"{hour:2d}:00  {count:5d}   {avg_duration:8.0f}ms   {max_duration:8.0f}ms"
            )

    async def analyze_inventory_changes(self, hours: int = 24):
        """Analyze inventory changes"""
        print(f"\n📦 Inventory Change Analysis (Last {hours} hours)")
        print("=" * 60)

        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Most reserved products
        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff_time}}},
            {
                "$group": {
                    "_id": "$product_id",
                    "total_reserved": {"$sum": "$quantity"},
                    "reservation_count": {"$sum": 1},
                }
            },
            {"$sort": {"total_reserved": -1}},
            {"$limit": 10},
        ]

        results = await self.db.inventory_reservations.aggregate(pipeline).to_list(None)

        if not results:
            print("No inventory reservations found")
            return

        print("Top 10 Reserved Products:")
        print("Product ID                           Reserved  Reservations")
        print("-" * 60)

        for result in results:
            product_id = result["_id"][:36]  # Truncate UUID
            total_reserved = result["total_reserved"]
            reservation_count = result["reservation_count"]

            print(f"{product_id:36} {total_reserved:8d}  {reservation_count:12d}")

    async def analyze_notification_delivery(self, hours: int = 24):
        """Analyze notification delivery"""
        print(f"\n📧 Notification Delivery Analysis (Last {hours} hours)")
        print("=" * 60)

        cutoff_time = datetime.now() - timedelta(hours=hours)

        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff_time}}},
            {
                "$group": {
                    "_id": {"type": "$notification_type", "status": "$status"},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.type": 1, "_id.status": 1}},
        ]

        results = await self.db.notifications.aggregate(pipeline).to_list(None)

        if not results:
            print("No notifications found")
            return

        # Group by type
        notification_types = {}
        for result in results:
            ntype = result["_id"]["type"]
            status = result["_id"]["status"]
            count = result["count"]

            if ntype not in notification_types:
                notification_types[ntype] = {}
            notification_types[ntype][status] = count

        for ntype, statuses in notification_types.items():
            total = sum(statuses.values())
            print(f"\n{ntype}:")
            for status, count in statuses.items():
                percentage = (count / total * 100) if total > 0 else 0
                print(f"  {status:10} {count:5d} ({percentage:5.1f}%)")

    async def generate_health_report(self, hours: int = 24):
        """Generate comprehensive health report"""
        print("🏥 SYSTEM HEALTH REPORT")
        print("=" * 80)
        print(f"Report Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Analysis Period: Last {hours} hours")

        await self.analyze_saga_performance(hours)
        await self.analyze_service_errors(hours)
        await self.analyze_order_patterns(hours)
        await self.analyze_performance_trends(hours)
        await self.analyze_inventory_changes(hours)
        await self.analyze_notification_delivery(hours)

        print("\n" + "=" * 80)
        print("🏥 END OF HEALTH REPORT")
        print("=" * 80)


async def main():
    parser = argparse.ArgumentParser(description="Analyze e-commerce saga system logs")
    parser.add_argument(
        "--hours", type=int, default=24, help="Hours of data to analyze"
    )
    parser.add_argument(
        "--report",
        choices=["health", "performance", "errors", "orders"],
        default="health",
        help="Type of report to generate",
    )

    args = parser.parse_args()

    analyzer = LogAnalyzer()

    try:
        await analyzer.connect()

        if args.report == "health":
            await analyzer.generate_health_report(args.hours)
        elif args.report == "performance":
            await analyzer.analyze_saga_performance(args.hours)
            await analyzer.analyze_performance_trends(args.hours)
        elif args.report == "errors":
            await analyzer.analyze_service_errors(args.hours)
        elif args.report == "orders":
            await analyzer.analyze_order_patterns(args.hours)
            await analyzer.analyze_inventory_changes(args.hours)

    except Exception as e:
        print(f"❌ Analysis failed: {str(e)}")
        sys.exit(1)
    finally:
        await analyzer.close()


if __name__ == "__main__":
    asyncio.run(main())

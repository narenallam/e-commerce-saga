#!/usr/bin/env python3
"""
Simple Monitoring Dashboard for E-commerce Saga System

Provides real-time monitoring of system health, performance metrics,
and alerts. Later to be replaced by full observability platforms.
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
import json
import sys
import os
from typing import Dict, List, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient


class MonitoringDashboard:
    def __init__(self):
        self.services = {
            "order": "http://localhost:8000",
            "inventory": "http://localhost:8001",
            "payment": "http://localhost:8002",
            "shipping": "http://localhost:8003",
            "notification": "http://localhost:8004",
        }
        self.db_client = None
        self.db = None
        self.alerts = []

    async def setup(self):
        """Setup monitoring"""
        self.db_client = AsyncIOMotorClient("mongodb://localhost:27017")
        self.db = self.db_client.ecommerce_saga

    async def close(self):
        """Close connections"""
        if self.db_client:
            self.db_client.close()

    async def check_service_health(
        self, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Check health of all services"""
        health_status = {}

        for service, url in self.services.items():
            try:
                start_time = datetime.now()
                async with session.get(f"{url}/health", timeout=5) as response:
                    duration = (datetime.now() - start_time).total_seconds() * 1000

                    health_status[service] = {
                        "status": "healthy" if response.status == 200 else "unhealthy",
                        "response_time_ms": duration,
                        "status_code": response.status,
                    }
            except Exception as e:
                health_status[service] = {
                    "status": "unreachable",
                    "error": str(e),
                    "response_time_ms": 0,
                }

        return health_status

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)

        # Recent saga performance
        saga_stats = await self.db.saga_logs.aggregate(
            [
                {"$match": {"created_at": {"$gte": one_hour_ago}}},
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1},
                        "avg_duration": {"$avg": "$total_duration_ms"},
                    }
                },
            ]
        ).to_list(None)

        # Recent order stats
        order_stats = await self.db.orders.aggregate(
            [
                {"$match": {"created_at": {"$gte": one_hour_ago}}},
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1},
                        "total_amount": {"$sum": "$total_amount"},
                    }
                },
            ]
        ).to_list(None)

        # Error rate
        total_sagas = sum(stat["count"] for stat in saga_stats)
        failed_sagas = sum(
            stat["count"]
            for stat in saga_stats
            if stat["_id"] in ["FAILED", "COMPENSATED"]
        )
        error_rate = (failed_sagas / total_sagas) if total_sagas > 0 else 0

        return {
            "saga_stats": saga_stats,
            "order_stats": order_stats,
            "total_sagas_1h": total_sagas,
            "error_rate_1h": error_rate,
            "timestamp": now.isoformat(),
        }

    async def check_alerts(self, health_status: Dict, metrics: Dict):
        """Check for alert conditions"""
        alerts = []

        # Service health alerts
        for service, status in health_status.items():
            if status["status"] != "healthy":
                alerts.append(
                    {
                        "type": "SERVICE_DOWN",
                        "service": service,
                        "message": f"Service {service} is {status['status']}",
                        "severity": "critical",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            elif status.get("response_time_ms", 0) > 5000:
                alerts.append(
                    {
                        "type": "SLOW_RESPONSE",
                        "service": service,
                        "message": f"Service {service} responding slowly ({status['response_time_ms']:.0f}ms)",
                        "severity": "warning",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        # Performance alerts
        error_rate = metrics.get("error_rate_1h", 0)
        if error_rate > 0.1:  # More than 10% error rate
            alerts.append(
                {
                    "type": "HIGH_ERROR_RATE",
                    "message": f"High error rate: {error_rate:.1%}",
                    "severity": "critical",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Check for long-running sagas
        cutoff_time = datetime.now() - timedelta(minutes=30)
        long_running = await self.db.saga_logs.count_documents(
            {"status": "IN_PROGRESS", "created_at": {"$lt": cutoff_time}}
        )

        if long_running > 0:
            alerts.append(
                {
                    "type": "LONG_RUNNING_SAGAS",
                    "message": f"{long_running} sagas running for more than 30 minutes",
                    "severity": "warning",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        self.alerts = alerts
        return alerts

    def print_dashboard(self, health_status: Dict, metrics: Dict, alerts: List):
        """Print monitoring dashboard"""
        # Clear screen (works on most terminals)
        os.system("clear" if os.name == "posix" else "cls")

        print("🖥️  E-COMMERCE SAGA MONITORING DASHBOARD")
        print("=" * 80)
        print(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Service Health
        print("🏥 SERVICE HEALTH")
        print("-" * 40)
        for service, status in health_status.items():
            status_emoji = {
                "healthy": "✅",
                "unhealthy": "❌",
                "unreachable": "🔴",
            }.get(status["status"], "❓")

            response_time = status.get("response_time_ms", 0)
            print(
                f"{status_emoji} {service:12} {status['status']:12} {response_time:6.0f}ms"
            )

        print()

        # Alerts
        if alerts:
            print("🚨 ACTIVE ALERTS")
            print("-" * 40)
            for alert in alerts:
                severity_emoji = "🚨" if alert["severity"] == "critical" else "⚠️"
                print(f"{severity_emoji} {alert['type']}: {alert['message']}")
        else:
            print("✅ NO ACTIVE ALERTS")

        print()

        # System Metrics
        print("📊 SYSTEM METRICS (Last Hour)")
        print("-" * 40)

        total_sagas = metrics.get("total_sagas_1h", 0)
        error_rate = metrics.get("error_rate_1h", 0)

        print(f"Total Sagas:    {total_sagas:6d}")
        print(f"Error Rate:     {error_rate:6.1%}")

        # Saga status breakdown
        saga_stats = metrics.get("saga_stats", [])
        for stat in saga_stats:
            status = stat["_id"]
            count = stat["count"]
            avg_duration = stat.get("avg_duration", 0) or 0
            print(f"{status:12}   {count:4d} ({avg_duration:6.0f}ms avg)")

        print()

        # Order metrics
        print("📦 ORDER METRICS (Last Hour)")
        print("-" * 40)

        order_stats = metrics.get("order_stats", [])
        total_orders = sum(stat["count"] for stat in order_stats)
        total_revenue = sum(stat.get("total_amount", 0) for stat in order_stats)

        print(f"Total Orders:   {total_orders:6d}")
        print(f"Total Revenue:  ${total_revenue:8.2f}")

        for stat in order_stats:
            status = stat["_id"]
            count = stat["count"]
            amount = stat.get("total_amount", 0) or 0
            print(f"{status:12}   {count:4d} (${amount:8.2f})")

        print()
        print("Press Ctrl+C to exit")
        print("=" * 80)

    async def run_monitoring_loop(self, interval: int = 30):
        """Run continuous monitoring"""
        print("🚀 Starting monitoring loop")
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    health_status = await self.check_service_health(session)
                    metrics = await self.get_system_metrics()
                    alerts = await self.check_alerts(health_status, metrics)
                    self.print_dashboard(health_status, metrics, alerts)
            except Exception as e:
                print(f"❌ Monitoring loop failed: {str(e)}")
            finally:
                await asyncio.sleep(interval)

    async def export_metrics(self, output_file: str = None):
        """Export current metrics to JSON file"""
        async with aiohttp.ClientSession() as session:
            health_status = await self.check_service_health(session)
            metrics = await self.get_system_metrics()
            alerts = await self.check_alerts(health_status, metrics)

            export_data = {
                "timestamp": datetime.now().isoformat(),
                "health_status": health_status,
                "metrics": metrics,
                "alerts": alerts,
            }

            if output_file:
                with open(output_file, "w") as f:
                    json.dump(export_data, f, indent=2)
                print(f"📊 Metrics exported to {output_file}")
            else:
                print(json.dumps(export_data, indent=2))


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="E-commerce Saga Monitoring Dashboard")
    parser.add_argument(
        "--interval", type=int, default=30, help="Refresh interval in seconds"
    )
    parser.add_argument(
        "--export", type=str, help="Export metrics to JSON file and exit"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")

    args = parser.parse_args()

    dashboard = MonitoringDashboard()

    try:
        await dashboard.setup()

        if args.export:
            await dashboard.export_metrics(args.export)
        elif args.once:
            async with aiohttp.ClientSession() as session:
                health_status = await dashboard.check_service_health(session)
                metrics = await dashboard.get_system_metrics()
                alerts = await dashboard.check_alerts(health_status, metrics)
                dashboard.print_dashboard(health_status, metrics, alerts)
        else:
            await dashboard.run_monitoring_loop(args.interval)

    except Exception as e:
        print(f"❌ Dashboard failed: {str(e)}")
        sys.exit(1)
    finally:
        await dashboard.close()


if __name__ == "__main__":
    asyncio.run(main())

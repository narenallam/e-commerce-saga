#!/usr/bin/env python3
"""
E-Commerce Saga Load Testing Script
Performs comprehensive load testing using generated test data.
"""

import asyncio
import aiohttp
import json
import time
import random
import argparse
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
import statistics

console = Console()


@dataclass
class LoadTestResult:
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = None
    errors: List[str] = None
    start_time: float = 0
    end_time: float = 0

    def __post_init__(self):
        if self.response_times is None:
            self.response_times = []
        if self.errors is None:
            self.errors = []

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def requests_per_second(self) -> float:
        if self.duration == 0:
            return 0.0
        return self.total_requests / self.duration

    @property
    def avg_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return statistics.mean(self.response_times)

    @property
    def p95_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return (
            statistics.quantiles(self.response_times, n=20)[18]
            if len(self.response_times) > 20
            else max(self.response_times)
        )


class LoadTester:
    def __init__(self, base_url: str = "http://localhost"):
        self.base_url = base_url
        self.service_ports = {
            "order": 8000,
            "inventory": 8001,
            "payment": 8002,
            "shipping": 8003,
            "notification": 8004,
            "saga": 9000,
        }
        self.test_data = {}
        self.results = LoadTestResult()

    async def load_test_data(self, data_dir: str = "./test-data"):
        """Load test data from generated files"""
        try:
            with open(f"{data_dir}/customers.json", "r") as f:
                self.test_data["customers"] = json.load(f)

            with open(f"{data_dir}/products.json", "r") as f:
                self.test_data["products"] = json.load(f)

            with open(f"{data_dir}/test_scenarios.json", "r") as f:
                self.test_data["scenarios"] = json.load(f)

            console.print("✅ Test data loaded successfully")
            console.print(f"👥 Customers: {len(self.test_data['customers'])}")
            console.print(f"📦 Products: {len(self.test_data['products'])}")

        except FileNotFoundError as e:
            console.print(f"❌ Test data not found: {e}")
            console.print(
                "💡 Run './scripts/test-data-generator.py' first to generate test data"
            )
            return False
        return True

    async def check_service_health(
        self, session: aiohttp.ClientSession
    ) -> Dict[str, bool]:
        """Check health of all services before testing"""
        health_status = {}

        for service, port in self.service_ports.items():
            try:
                url = f"{self.base_url}:{port}/health"
                async with session.get(url, timeout=5) as response:
                    health_status[service] = response.status == 200
            except Exception:
                health_status[service] = False

        return health_status

    async def create_order(
        self, session: aiohttp.ClientSession, order_data: Dict[str, Any]
    ) -> tuple[bool, float, str]:
        """Create a single order and measure response time"""
        start_time = time.time()

        try:
            url = f"{self.base_url}:{self.service_ports['order']}/orders"
            async with session.post(url, json=order_data, timeout=30) as response:
                response_time = time.time() - start_time
                success = response.status in [200, 201]
                error_msg = "" if success else f"HTTP {response.status}"
                return success, response_time, error_msg

        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            return False, response_time, "TIMEOUT"
        except Exception as e:
            response_time = time.time() - start_time
            return False, response_time, str(e)

    def generate_random_order(self) -> Dict[str, Any]:
        """Generate a random order from test data"""
        customer = random.choice(self.test_data["customers"])
        products = random.sample(
            [
                p
                for p in self.test_data["products"]
                if p["is_active"] and p["stock"] > 0
            ],
            random.randint(1, 3),
        )

        items = []
        total_amount = 0

        for product in products:
            quantity = random.randint(1, min(3, product["stock"]))
            item_total = product["price"] * quantity

            items.append(
                {
                    "product_id": product["id"],
                    "quantity": quantity,
                    "unit_price": product["price"],
                }
            )
            total_amount += item_total

        order = {
            "customer_id": customer["id"],
            "items": items,
            "payment_method": random.choice(["credit_card", "debit_card", "paypal"]),
            "shipping_address": customer["shipping_address"],
            "billing_address": customer["billing_address"],
            "total_amount": round(total_amount, 2),
        }

        return order

    async def run_user_simulation(
        self,
        session: aiohttp.ClientSession,
        user_id: int,
        orders_per_minute: int,
        duration_minutes: int,
        progress_task,
    ) -> List[tuple]:
        """Simulate a single user's order activity"""
        results = []
        end_time = time.time() + (duration_minutes * 60)
        order_interval = 60 / orders_per_minute  # seconds between orders

        while time.time() < end_time:
            order_data = self.generate_random_order()
            success, response_time, error = await self.create_order(session, order_data)

            results.append((success, response_time, error))

            # Update progress
            if hasattr(progress_task, "advance"):
                progress_task.advance()

            # Wait before next order
            await asyncio.sleep(order_interval)

        return results

    async def run_load_test(
        self,
        concurrent_users: int,
        orders_per_minute: int,
        duration_minutes: int,
        show_progress: bool = True,
    ):
        """Execute load test with specified parameters"""
        console.print(f"\n🚀 Starting load test...")
        console.print(f"👥 Concurrent users: {concurrent_users}")
        console.print(f"📊 Orders per minute per user: {orders_per_minute}")
        console.print(f"⏱️  Duration: {duration_minutes} minutes")

        # Reset results
        self.results = LoadTestResult()
        self.results.start_time = time.time()

        connector = aiohttp.TCPConnector(limit=concurrent_users * 2)
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout
        ) as session:
            # Check service health first
            console.print("\n🔍 Checking service health...")
            health_status = await self.check_service_health(session)

            healthy_services = sum(health_status.values())
            total_services = len(health_status)

            if healthy_services < total_services:
                console.print(
                    f"⚠️  Warning: {total_services - healthy_services} services are unhealthy"
                )
                for service, healthy in health_status.items():
                    status = "✅" if healthy else "❌"
                    console.print(f"  {status} {service}")

                if healthy_services == 0:
                    console.print("❌ No services are healthy. Aborting test.")
                    return
            else:
                console.print("✅ All services are healthy")

            # Start load test
            console.print(f"\n🎯 Launching {concurrent_users} virtual users...")

            if show_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console,
                ) as progress:

                    expected_requests = (
                        concurrent_users * orders_per_minute * duration_minutes
                    )
                    task = progress.add_task(
                        "Load testing in progress...", total=expected_requests
                    )

                    # Create user simulation tasks
                    user_tasks = [
                        self.run_user_simulation(
                            session, i, orders_per_minute, duration_minutes, task
                        )
                        for i in range(concurrent_users)
                    ]

                    # Execute all user simulations concurrently
                    user_results = await asyncio.gather(
                        *user_tasks, return_exceptions=True
                    )
            else:
                # Run without progress bar
                user_tasks = [
                    self.run_user_simulation(
                        session, i, orders_per_minute, duration_minutes, None
                    )
                    for i in range(concurrent_users)
                ]
                user_results = await asyncio.gather(*user_tasks, return_exceptions=True)

        self.results.end_time = time.time()

        # Process results
        for user_result in user_results:
            if isinstance(user_result, Exception):
                console.print(f"⚠️  User simulation error: {user_result}")
                continue

            for success, response_time, error in user_result:
                self.results.total_requests += 1
                self.results.response_times.append(response_time)

                if success:
                    self.results.successful_requests += 1
                else:
                    self.results.failed_requests += 1
                    self.results.errors.append(error)

    def generate_load_test_report(self) -> Table:
        """Generate a detailed load test report"""
        table = Table(title="🏆 Load Test Results Summary", style="cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="green")
        table.add_column("Status", style="yellow")

        # Basic metrics
        table.add_row("Total Requests", str(self.results.total_requests), "📊")
        table.add_row(
            "Successful Requests", str(self.results.successful_requests), "✅"
        )
        table.add_row(
            "Failed Requests",
            str(self.results.failed_requests),
            "❌" if self.results.failed_requests > 0 else "✅",
        )
        table.add_row(
            "Success Rate",
            f"{self.results.success_rate:.2f}%",
            (
                "✅"
                if self.results.success_rate >= 95
                else "⚠️" if self.results.success_rate >= 90 else "❌"
            ),
        )

        # Performance metrics
        table.add_row("Duration", f"{self.results.duration:.2f} seconds", "⏱️")
        table.add_row(
            "Requests/Second", f"{self.results.requests_per_second:.2f}", "🚀"
        )
        table.add_row(
            "Avg Response Time",
            f"{self.results.avg_response_time*1000:.2f} ms",
            (
                "✅"
                if self.results.avg_response_time < 0.5
                else "⚠️" if self.results.avg_response_time < 1.0 else "❌"
            ),
        )
        table.add_row(
            "95th Percentile",
            f"{self.results.p95_response_time*1000:.2f} ms",
            (
                "✅"
                if self.results.p95_response_time < 1.0
                else "⚠️" if self.results.p95_response_time < 2.0 else "❌"
            ),
        )

        if self.results.response_times:
            table.add_row(
                "Min Response Time",
                f"{min(self.results.response_times)*1000:.2f} ms",
                "⚡",
            )
            table.add_row(
                "Max Response Time",
                f"{max(self.results.response_times)*1000:.2f} ms",
                "🐌",
            )

        return table

    def generate_error_report(self) -> Table:
        """Generate error analysis report"""
        if not self.results.errors:
            return None

        error_counts = {}
        for error in self.results.errors:
            error_counts[error] = error_counts.get(error, 0) + 1

        table = Table(title="❌ Error Analysis", style="red")
        table.add_column("Error Type", style="bold")
        table.add_column("Count", style="red")
        table.add_column("Percentage", style="yellow")

        for error, count in sorted(
            error_counts.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / self.results.total_requests) * 100
            table.add_row(error, str(count), f"{percentage:.2f}%")

        return table

    async def run_predefined_scenarios(self, data_dir: str = "./test-data"):
        """Run predefined test scenarios from test data"""
        if "scenarios" not in self.test_data:
            console.print("❌ No test scenarios found in data")
            return

        console.print("\n🧪 Running Predefined Test Scenarios")
        console.print("=" * 50)

        load_scenarios = self.test_data["scenarios"].get("load_test_data", [])

        for scenario in load_scenarios:
            console.print(f"\n🎯 Scenario: {scenario['test_name']}")
            console.print(
                f"Users: {scenario['concurrent_users']}, Duration: {scenario['duration_minutes']}min"
            )

            await self.run_load_test(
                concurrent_users=scenario["concurrent_users"],
                orders_per_minute=scenario["orders_per_user_per_minute"],
                duration_minutes=scenario["duration_minutes"],
            )

            # Display results
            console.print(self.generate_load_test_report())

            if self.results.errors:
                error_table = self.generate_error_report()
                if error_table:
                    console.print(error_table)

            # Check if scenario passed
            success_threshold = scenario.get("success_rate_threshold", 95.0)
            if self.results.success_rate >= success_threshold:
                console.print(
                    f"✅ Scenario PASSED (Success rate: {self.results.success_rate:.2f}% >= {success_threshold}%)"
                )
            else:
                console.print(
                    f"❌ Scenario FAILED (Success rate: {self.results.success_rate:.2f}% < {success_threshold}%)"
                )

            console.print("-" * 50)


async def main():
    parser = argparse.ArgumentParser(description="Load test e-commerce saga system")
    parser.add_argument(
        "--users", type=int, default=10, help="Number of concurrent users"
    )
    parser.add_argument(
        "--rate", type=int, default=2, help="Orders per minute per user"
    )
    parser.add_argument(
        "--duration", type=int, default=5, help="Test duration in minutes"
    )
    parser.add_argument(
        "--base-url", default="http://localhost", help="Base URL for services"
    )
    parser.add_argument("--data-dir", default="./test-data", help="Test data directory")
    parser.add_argument(
        "--scenarios",
        action="store_true",
        help="Run predefined scenarios instead of custom test",
    )
    parser.add_argument(
        "--no-progress", action="store_true", help="Disable progress bar"
    )

    args = parser.parse_args()

    tester = LoadTester(base_url=args.base_url)

    # Load test data
    if not await tester.load_test_data(args.data_dir):
        return

    if args.scenarios:
        # Run predefined scenarios
        await tester.run_predefined_scenarios(args.data_dir)
    else:
        # Run custom load test
        await tester.run_load_test(
            concurrent_users=args.users,
            orders_per_minute=args.rate,
            duration_minutes=args.duration,
            show_progress=not args.no_progress,
        )

        # Display results
        console.print("\n" + "=" * 60)
        console.print(tester.generate_load_test_report())

        if tester.results.errors:
            error_table = tester.generate_error_report()
            if error_table:
                console.print("\n")
                console.print(error_table)

        # Performance assessment
        console.print("\n🎯 Performance Assessment:")
        if tester.results.success_rate >= 99:
            console.print("🏆 EXCELLENT: System performed exceptionally well")
        elif tester.results.success_rate >= 95:
            console.print("✅ GOOD: System meets performance requirements")
        elif tester.results.success_rate >= 90:
            console.print("⚠️  ACCEPTABLE: System has some issues but functional")
        else:
            console.print("❌ POOR: System has significant performance problems")


if __name__ == "__main__":
    asyncio.run(main())

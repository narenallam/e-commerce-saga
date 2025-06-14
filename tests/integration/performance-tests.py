#!/usr/bin/env python3
"""
Performance Functional Tests for E-Commerce Saga System
Focus on response times, throughput, and system performance
"""

import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress
from rich import box

console = Console()


@dataclass
class PerformanceResult:
    """Performance test result"""

    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    throughput: float  # requests per second
    duration: float


class PerformanceTester:
    """Performance testing for e-commerce services"""

    def __init__(self):
        self.base_urls = {
            "order": "http://localhost:8000",
            "inventory": "http://localhost:8001",
            "payment": "http://localhost:8002",
            "shipping": "http://localhost:8003",
            "notification": "http://localhost:8004",
            "saga": "http://localhost:9000",
        }

    async def make_timed_request(
        self, session: aiohttp.ClientSession, method: str, url: str, **kwargs
    ) -> Dict[str, Any]:
        """Make a timed HTTP request"""
        start_time = time.time()
        try:
            async with session.request(method, url, **kwargs) as response:
                duration = time.time() - start_time
                return {
                    "success": 200 <= response.status < 300,
                    "status": response.status,
                    "duration": duration,
                    "error": None,
                }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "success": False,
                "status": 0,
                "duration": duration,
                "error": str(e),
            }

    async def health_check_performance_test(
        self, concurrent_requests: int = 50, total_requests: int = 200
    ) -> PerformanceResult:
        """Test health endpoint performance"""
        console.print(
            f"🩺 Testing health endpoint performance ({concurrent_requests} concurrent, {total_requests} total)..."
        )

        start_time = time.time()
        semaphore = asyncio.Semaphore(concurrent_requests)
        results = []

        async def make_health_request(
            session: aiohttp.ClientSession, service: str, url: str
        ):
            async with semaphore:
                return await self.make_timed_request(session, "GET", f"{url}/health")

        async with aiohttp.ClientSession() as session:
            tasks = []

            for i in range(total_requests):
                service_name = list(self.base_urls.keys())[i % len(self.base_urls)]
                service_url = self.base_urls[service_name]
                tasks.append(make_health_request(session, service_name, service_url))

            with Progress() as progress:
                task_id = progress.add_task("Health checks...", total=total_requests)

                completed = 0
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    results.append(result)
                    completed += 1
                    progress.update(task_id, completed=completed)

        # Calculate statistics
        total_duration = time.time() - start_time
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        response_times = [r["duration"] for r in successful]

        if response_times:
            avg_time = statistics.mean(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
            p95_time = (
                statistics.quantiles(response_times, n=20)[18]
                if len(response_times) > 1
                else avg_time
            )
        else:
            avg_time = min_time = max_time = p95_time = 0.0

        throughput = total_requests / total_duration if total_duration > 0 else 0

        return PerformanceResult(
            test_name="Health Check Performance",
            total_requests=total_requests,
            successful_requests=len(successful),
            failed_requests=len(failed),
            avg_response_time=avg_time,
            min_response_time=min_time,
            max_response_time=max_time,
            p95_response_time=p95_time,
            throughput=throughput,
            duration=total_duration,
        )

    async def inventory_query_performance_test(
        self, concurrent_requests: int = 30, total_requests: int = 150
    ) -> PerformanceResult:
        """Test inventory query performance"""
        console.print(
            f"📦 Testing inventory query performance ({concurrent_requests} concurrent, {total_requests} total)..."
        )

        start_time = time.time()
        semaphore = asyncio.Semaphore(concurrent_requests)
        results = []

        # Different query endpoints to test
        endpoints = [
            "/api/inventory/statistics",
            "/api/inventory/products",
            "/api/inventory/categories",
            "/api/inventory/low-stock?threshold=10",
        ]

        async def make_inventory_request(session: aiohttp.ClientSession, endpoint: str):
            async with semaphore:
                url = f"{self.base_urls['inventory']}{endpoint}"
                return await self.make_timed_request(session, "GET", url)

        async with aiohttp.ClientSession() as session:
            tasks = []

            for i in range(total_requests):
                endpoint = endpoints[i % len(endpoints)]
                tasks.append(make_inventory_request(session, endpoint))

            with Progress() as progress:
                task_id = progress.add_task(
                    "Inventory queries...", total=total_requests
                )

                completed = 0
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    results.append(result)
                    completed += 1
                    progress.update(task_id, completed=completed)

        # Calculate statistics
        total_duration = time.time() - start_time
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        response_times = [r["duration"] for r in successful]

        if response_times:
            avg_time = statistics.mean(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
            p95_time = (
                statistics.quantiles(response_times, n=20)[18]
                if len(response_times) > 1
                else avg_time
            )
        else:
            avg_time = min_time = max_time = p95_time = 0.0

        throughput = total_requests / total_duration if total_duration > 0 else 0

        return PerformanceResult(
            test_name="Inventory Query Performance",
            total_requests=total_requests,
            successful_requests=len(successful),
            failed_requests=len(failed),
            avg_response_time=avg_time,
            min_response_time=min_time,
            max_response_time=max_time,
            p95_response_time=p95_time,
            throughput=throughput,
            duration=total_duration,
        )

    async def order_creation_performance_test(
        self, concurrent_requests: int = 20, total_requests: int = 100
    ) -> PerformanceResult:
        """Test order creation performance"""
        console.print(
            f"🛒 Testing order creation performance ({concurrent_requests} concurrent, {total_requests} total)..."
        )

        start_time = time.time()
        semaphore = asyncio.Semaphore(concurrent_requests)
        results = []

        async def make_order_request(session: aiohttp.ClientSession, order_num: int):
            async with semaphore:
                order_data = {
                    "customer_id": f"perf.test.{order_num}@example.com",
                    "items": [
                        {
                            "product_id": f"perf_product_{order_num % 10}",
                            "quantity": 1,
                            "price": 29.99,
                        }
                    ],
                    "total_amount": 29.99,
                    "shipping_address": {
                        "street": f"{100 + order_num} Perf Street",
                        "city": "Performance City",
                        "state": "PC",
                        "zip_code": "99999",
                        "country": "USA",
                    },
                }

                url = f"{self.base_urls['order']}/api/orders"
                return await self.make_timed_request(
                    session,
                    "POST",
                    url,
                    json=order_data,
                    headers={"Content-Type": "application/json"},
                )

        async with aiohttp.ClientSession() as session:
            tasks = []

            for i in range(total_requests):
                tasks.append(make_order_request(session, i))

            with Progress() as progress:
                task_id = progress.add_task("Order creation...", total=total_requests)

                completed = 0
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    results.append(result)
                    completed += 1
                    progress.update(task_id, completed=completed)

        # Calculate statistics
        total_duration = time.time() - start_time
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        response_times = [r["duration"] for r in successful]

        if response_times:
            avg_time = statistics.mean(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
            p95_time = (
                statistics.quantiles(response_times, n=20)[18]
                if len(response_times) > 1
                else avg_time
            )
        else:
            avg_time = min_time = max_time = p95_time = 0.0

        throughput = total_requests / total_duration if total_duration > 0 else 0

        return PerformanceResult(
            test_name="Order Creation Performance",
            total_requests=total_requests,
            successful_requests=len(successful),
            failed_requests=len(failed),
            avg_response_time=avg_time,
            min_response_time=min_time,
            max_response_time=max_time,
            p95_response_time=p95_time,
            throughput=throughput,
            duration=total_duration,
        )

    async def mixed_workload_performance_test(
        self, duration_seconds: int = 60
    ) -> PerformanceResult:
        """Test mixed workload performance"""
        console.print(
            f"🔄 Testing mixed workload performance ({duration_seconds}s duration)..."
        )

        start_time = time.time()
        end_time = start_time + duration_seconds
        results = []

        # Define workload mix
        workload_mix = [
            (
                "GET",
                f"{self.base_urls['inventory']}/api/inventory/statistics",
                None,
                40,
            ),  # 40% inventory queries
            ("GET", f"{self.base_urls['order']}/health", None, 20),  # 20% health checks
            (
                "GET",
                f"{self.base_urls['payment']}/api/payments/statistics",
                None,
                15,
            ),  # 15% payment queries
            (
                "GET",
                f"{self.base_urls['shipping']}/api/shipments/statistics",
                None,
                15,
            ),  # 15% shipping queries
            (
                "GET",
                f"{self.base_urls['notification']}/api/notifications/statistics",
                None,
                10,
            ),  # 10% notification queries
        ]

        # Create weighted list
        weighted_requests = []
        for method, url, data, weight in workload_mix:
            weighted_requests.extend([(method, url, data)] * weight)

        semaphore = asyncio.Semaphore(25)  # Limit concurrent requests

        async def make_workload_request(session: aiohttp.ClientSession):
            async with semaphore:
                import random

                method, url, data = random.choice(weighted_requests)
                kwargs = (
                    {"json": data, "headers": {"Content-Type": "application/json"}}
                    if data
                    else {}
                )
                return await self.make_timed_request(session, method, url, **kwargs)

        async with aiohttp.ClientSession() as session:
            tasks = []
            request_count = 0

            with Progress() as progress:
                task_id = progress.add_task("Mixed workload...", total=duration_seconds)

                while time.time() < end_time:
                    # Add new requests
                    for _ in range(5):  # Add 5 requests per batch
                        if time.time() < end_time:
                            task = asyncio.create_task(make_workload_request(session))
                            tasks.append(task)
                            request_count += 1

                    # Collect completed tasks
                    if tasks:
                        done, pending = await asyncio.wait(
                            tasks, timeout=1.0, return_when=asyncio.FIRST_COMPLETED
                        )
                        for task in done:
                            result = await task
                            results.append(result)
                            tasks.remove(task)

                    # Update progress
                    elapsed = time.time() - start_time
                    progress.update(task_id, completed=elapsed)

                # Wait for remaining tasks
                if tasks:
                    remaining_results = await asyncio.gather(
                        *tasks, return_exceptions=True
                    )
                    for result in remaining_results:
                        if isinstance(result, dict):
                            results.append(result)

        # Calculate statistics
        total_duration = time.time() - start_time
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        response_times = [r["duration"] for r in successful]

        if response_times:
            avg_time = statistics.mean(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
            p95_time = (
                statistics.quantiles(response_times, n=20)[18]
                if len(response_times) > 1
                else avg_time
            )
        else:
            avg_time = min_time = max_time = p95_time = 0.0

        throughput = len(results) / total_duration if total_duration > 0 else 0

        return PerformanceResult(
            test_name="Mixed Workload Performance",
            total_requests=len(results),
            successful_requests=len(successful),
            failed_requests=len(failed),
            avg_response_time=avg_time,
            min_response_time=min_time,
            max_response_time=max_time,
            p95_response_time=p95_time,
            throughput=throughput,
            duration=total_duration,
        )

    async def run_all_performance_tests(self) -> List[PerformanceResult]:
        """Run all performance tests"""
        console.print(
            Panel.fit(
                "[bold cyan]⚡ PERFORMANCE FUNCTIONAL TESTS[/bold cyan]\n"
                "[dim]Testing system performance and response times[/dim]",
                box=box.DOUBLE,
            )
        )

        results = []

        # Run individual performance tests
        health_result = await self.health_check_performance_test()
        results.append(health_result)

        inventory_result = await self.inventory_query_performance_test()
        results.append(inventory_result)

        order_result = await self.order_creation_performance_test()
        results.append(order_result)

        mixed_result = await self.mixed_workload_performance_test()
        results.append(mixed_result)

        return results

    def generate_performance_report(self, results: List[PerformanceResult]) -> None:
        """Generate performance test report"""
        if not results:
            console.print("❌ No performance results to report")
            return

        # Summary table
        summary_table = Table(title="⚡ Performance Test Summary", box=box.ROUNDED)
        summary_table.add_column("Test", style="cyan", width=25)
        summary_table.add_column("Requests", style="white", justify="right", width=10)
        summary_table.add_column(
            "Success Rate", style="green", justify="right", width=12
        )
        summary_table.add_column("Avg Time", style="yellow", justify="right", width=10)
        summary_table.add_column("P95 Time", style="magenta", justify="right", width=10)
        summary_table.add_column("Throughput", style="blue", justify="right", width=12)

        for result in results:
            success_rate = (
                (result.successful_requests / result.total_requests * 100)
                if result.total_requests > 0
                else 0
            )

            summary_table.add_row(
                result.test_name,
                str(result.total_requests),
                f"{success_rate:.1f}%",
                f"{result.avg_response_time*1000:.1f}ms",
                f"{result.p95_response_time*1000:.1f}ms",
                f"{result.throughput:.1f} req/s",
            )

        console.print(summary_table)

        # Detailed statistics table
        details_table = Table(
            title="📊 Detailed Performance Statistics", box=box.ROUNDED, show_lines=True
        )
        details_table.add_column("Test", style="cyan", width=25)
        details_table.add_column("Min Time", style="green", justify="right", width=10)
        details_table.add_column("Max Time", style="red", justify="right", width=10)
        details_table.add_column("Failed", style="red", justify="right", width=8)
        details_table.add_column("Duration", style="blue", justify="right", width=10)

        for result in results:
            details_table.add_row(
                result.test_name,
                f"{result.min_response_time*1000:.1f}ms",
                f"{result.max_response_time*1000:.1f}ms",
                str(result.failed_requests),
                f"{result.duration:.1f}s",
            )

        console.print(details_table)

        # Performance analysis
        avg_success_rate = (
            sum(r.successful_requests / r.total_requests for r in results)
            / len(results)
            * 100
        )
        avg_response_time = (
            sum(r.avg_response_time for r in results) / len(results) * 1000
        )
        total_throughput = sum(r.throughput for r in results)

        console.print(f"\n📈 [bold]Overall Performance Analysis:[/bold]")
        console.print(f"   Average Success Rate: {avg_success_rate:.1f}%")
        console.print(f"   Average Response Time: {avg_response_time:.1f}ms")
        console.print(f"   Combined Throughput: {total_throughput:.1f} req/s")

        # Performance verdict
        if avg_success_rate >= 99 and avg_response_time <= 100:
            console.print(
                Panel.fit(
                    "[bold green]🏆 EXCELLENT PERFORMANCE![/bold green]\n"
                    "[dim]System demonstrates high performance and reliability[/dim]",
                    box=box.DOUBLE,
                )
            )
        elif avg_success_rate >= 95 and avg_response_time <= 500:
            console.print(
                Panel.fit(
                    "[bold yellow]✅ GOOD PERFORMANCE[/bold yellow]\n"
                    "[dim]System performance is acceptable with room for optimization[/dim]",
                    box=box.DOUBLE,
                )
            )
        else:
            console.print(
                Panel.fit(
                    "[bold red]⚠️ PERFORMANCE ISSUES DETECTED[/bold red]\n"
                    "[dim]System may need performance optimization[/dim]",
                    box=box.DOUBLE,
                )
            )


async def main():
    """Main performance test execution"""
    tester = PerformanceTester()

    try:
        # Run all performance tests
        results = await tester.run_all_performance_tests()

        # Generate report
        console.print("\n" + "=" * 80)
        tester.generate_performance_report(results)

    except Exception as e:
        console.print(f"❌ Performance tests failed: {e}")
        return


if __name__ == "__main__":
    asyncio.run(main())

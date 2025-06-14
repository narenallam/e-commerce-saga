#!/usr/bin/env python3
"""
Quick Functional Test Suite for E-Commerce Saga System
Demonstrates testing scenarios from Testing.md documentation
"""

import asyncio
import aiohttp
import time
import random
import json
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel

console = Console()


class QuickTester:
    def __init__(self):
        self.base_url = "http://localhost"
        self.service_ports = {
            "order": 8000,
            "inventory": 8001,
            "payment": 8002,
            "shipping": 8003,
            "notification": 8004,
            "saga": 9000,
        }
        self.test_results = []

    async def test_service_health(self, session: aiohttp.ClientSession):
        """Test all service health endpoints"""
        console.print("🧪 [bold blue]Testing Service Health[/bold blue]")

        results = []
        for service, port in self.service_ports.items():
            try:
                url = f"{self.base_url}:{port}/health"
                start_time = time.time()
                async with session.get(url, timeout=5) as response:
                    duration = (time.time() - start_time) * 1000
                    if response.status == 200:
                        results.append((service, "✅ Healthy", f"{duration:.1f}ms"))
                    else:
                        results.append(
                            (service, f"❌ HTTP {response.status}", f"{duration:.1f}ms")
                        )
            except Exception as e:
                results.append((service, f"❌ {str(e)[:30]}...", "timeout"))

        # Display results
        table = Table(title="🩺 Service Health Check Results")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Response Time", style="green")

        for service, status, response_time in results:
            table.add_row(service, status, response_time)

        console.print(table)

        healthy_count = sum(1 for _, status, _ in results if "✅" in status)
        return healthy_count, len(self.service_ports)

    async def test_concurrent_health_checks(self, session: aiohttp.ClientSession):
        """Test concurrent health checks - simulates load"""
        console.print(
            "\n🧪 [bold blue]Testing Concurrent Health Checks (Load Simulation)[/bold blue]"
        )

        concurrent_requests = 20
        start_time = time.time()

        # Create concurrent health check requests
        tasks = []
        for _ in range(concurrent_requests):
            service = random.choice(list(self.service_ports.keys()))
            port = self.service_ports[service]
            url = f"{self.base_url}:{port}/health"
            tasks.append(session.get(url, timeout=5))

        # Execute all requests concurrently
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze results
        successful = 0
        failed = 0

        for response in responses:
            if isinstance(response, Exception):
                failed += 1
            else:
                if response.status == 200:
                    successful += 1
                else:
                    failed += 1
                response.close()

        console.print(f"  📊 Results: {successful}/{concurrent_requests} successful")
        console.print(f"  ⏱️ Total time: {total_time:.2f}s")
        console.print(
            f"  🚀 Avg response time: {(total_time/concurrent_requests)*1000:.1f}ms"
        )

        return successful >= concurrent_requests * 0.9  # 90% success rate

    async def test_database_connectivity(self):
        """Test database connectivity and validate test data"""
        console.print("\n🧪 [bold blue]Testing Database & Test Data[/bold blue]")

        try:
            from motor.motor_asyncio import AsyncIOMotorClient

            client = AsyncIOMotorClient("mongodb://localhost:27017")
            db = client.ecommerce_saga

            # Check collections and count documents
            collections = [
                "customers",
                "inventory",
                "orders",
                "payments",
                "notifications",
                "saga_logs",
            ]
            collection_counts = {}

            for collection_name in collections:
                try:
                    count = await db[collection_name].count_documents({})
                    collection_counts[collection_name] = count
                    console.print(f"  ✅ {collection_name}: {count} documents")
                except Exception as e:
                    console.print(f"  ❌ {collection_name}: {str(e)}")
                    collection_counts[collection_name] = 0

            # Show some sample data
            orders = await db.orders.find().limit(3).to_list(3)
            if orders:
                console.print(f"  📋 Sample orders: {len(orders)} found")
                for order in orders:
                    console.print(
                        f"    • Order {order.get('order_id', 'unknown')}: {order.get('status', 'unknown')} - ${order.get('total_amount', 0):.2f}"
                    )

            client.close()

            total_documents = sum(collection_counts.values())
            console.print(f"\n📊 Database Summary: {total_documents} total documents")

            return total_documents > 0

        except ImportError:
            console.print("  ❌ MongoDB driver (motor) not available")
            return False
        except Exception as e:
            console.print(f"  ❌ Database connection failed: {str(e)}")
            return False

    async def test_api_endpoints(self, session: aiohttp.ClientSession):
        """Test various API endpoints"""
        console.print("\n🧪 [bold blue]Testing API Endpoints[/bold blue]")

        # Test different endpoints
        endpoints = [
            ("order", "/health", "GET"),
            ("saga", "/health", "GET"),
            ("inventory", "/health", "GET"),
            ("payment", "/health", "GET"),
            ("shipping", "/health", "GET"),
            ("notification", "/health", "GET"),
        ]

        working_endpoints = 0

        for service, path, method in endpoints:
            try:
                port = self.service_ports[service]
                url = f"{self.base_url}:{port}{path}"

                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        working_endpoints += 1
                        console.print(f"  ✅ {service}{path}: OK ({response.status})")
                    else:
                        console.print(f"  ⚠️ {service}{path}: HTTP {response.status}")
            except Exception as e:
                console.print(f"  ❌ {service}{path}: {str(e)}")

        console.print(
            f"\n📊 API Summary: {working_endpoints}/{len(endpoints)} endpoints working"
        )
        return working_endpoints >= len(endpoints) * 0.9

    async def run_quick_tests(self):
        """Run all quick tests"""
        console.print("\n🚀 [bold green]E-Commerce Saga Quick Test Suite[/bold green]")
        console.print("=" * 60)

        async with aiohttp.ClientSession() as session:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console,
            ) as progress:

                # Test 1: Service Health
                task = progress.add_task("Running health checks...", total=4)
                healthy_count, total_services = await self.test_service_health(session)
                health_passed = healthy_count == total_services
                progress.advance(task)

                # Test 2: Concurrent Load
                progress.update(task, description="Testing concurrent load...")
                load_passed = await self.test_concurrent_health_checks(session)
                progress.advance(task)

                # Test 3: Database
                progress.update(task, description="Testing database...")
                db_passed = await self.test_database_connectivity()
                progress.advance(task)

                # Test 4: API Endpoints
                progress.update(task, description="Testing API endpoints...")
                api_passed = await self.test_api_endpoints(session)
                progress.advance(task)

        # Summary
        console.print("\n🎯 [bold green]Test Summary[/bold green]")
        console.print("=" * 40)

        tests = [
            (
                "Service Health",
                health_passed,
                f"{healthy_count}/{total_services} services",
            ),
            ("Concurrent Load", load_passed, "20 concurrent requests"),
            ("Database Connectivity", db_passed, "MongoDB + test data"),
            ("API Endpoints", api_passed, "Health endpoints"),
        ]

        passed_count = sum(1 for _, passed, _ in tests if passed)

        for test_name, passed, details in tests:
            status = "✅ PASSED" if passed else "❌ FAILED"
            console.print(f"  {test_name}: {status} ({details})")

        success_rate = (passed_count / len(tests)) * 100
        console.print(
            f"\nOverall: {passed_count}/{len(tests)} tests passed ({success_rate:.1f}%)"
        )

        if success_rate >= 90:
            console.print(
                "\n🏆 [bold green]EXCELLENT! System is functioning very well.[/bold green]"
            )
        elif success_rate >= 70:
            console.print(
                "\n✅ [bold yellow]GOOD! System is working with minor issues.[/bold yellow]"
            )
        else:
            console.print(
                "\n❌ [bold red]ISSUES DETECTED! System needs attention.[/bold red]"
            )

        # Next steps
        console.print("\n💡 [cyan]Suggested next steps:[/cyan]")
        if success_rate >= 90:
            console.print("  • Run load tests: make load-test")
            console.print("  • Run chaos tests: make chaos-pod")
            console.print(
                "  • Generate more test data: python tools/test_data_generator.py"
            )
        else:
            console.print(
                "  • Check service logs: kubectl logs -f deployment/order-service -n e-commerce-saga"
            )
            console.print("  • Restart services: make dev-reset")


async def main():
    console.print(
        Panel.fit(
            "[bold cyan]🧪 E-Commerce Saga Quick Test Suite[/bold cyan]\n"
            "[yellow]Validating functionality and technical aspects[/yellow]",
            border_style="cyan",
        )
    )

    tester = QuickTester()
    await tester.run_quick_tests()

    console.print("\n✨ [bold green]Quick testing complete![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())

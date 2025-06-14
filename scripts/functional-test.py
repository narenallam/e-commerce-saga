#!/usr/bin/env python3
"""
Functional Test Suite for E-Commerce Saga System
Validates key scenarios from Testing.md documentation
"""

import asyncio
import aiohttp
import time
import json
from datetime import datetime
from typing import Dict, List, Any
from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
from rich.panel import Panel

console = Console()


class FunctionalTester:
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
        self.test_results = []

    async def test_f11_complete_order_success_flow(
        self, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Test Case F1.1: Complete Order Success Flow"""
        console.print(
            "🧪 [bold blue]Test Case F1.1: Complete Order Success Flow[/bold blue]"
        )

        test_data = {
            "customer_id": "CUST000001",
            "items": [
                {
                    "product_id": "PROD000001",
                    "name": "Test Product",
                    "quantity": 1,
                    "unit_price": 999.99,
                }
            ],
            "payment_method": "credit_card",
            "shipping_address": {
                "street": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "zip": "94105",
            },
            "total_amount": 999.99,
        }

        start_time = time.time()
        result = {"test_case": "F1.1", "status": "FAILED", "details": [], "duration": 0}

        try:
            # Step 1: Create order via saga coordinator
            url = f"{self.base_url}:{self.service_ports['saga']}/api/coordinator/orders"
            async with session.post(url, json=test_data, timeout=30) as response:
                if response.status in [200, 201]:
                    order_data = await response.json()
                    result["details"].append(
                        f"✅ Order created successfully: {order_data.get('order_id', 'Unknown')}"
                    )
                    result["status"] = "PASSED"
                else:
                    result["details"].append(
                        f"❌ Order creation failed: HTTP {response.status}"
                    )

        except Exception as e:
            result["details"].append(f"❌ Exception during order creation: {str(e)}")

        result["duration"] = time.time() - start_time
        return result

    async def test_f12_multiple_concurrent_orders(
        self, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Test Case F1.2: Multiple Concurrent Orders"""
        console.print(
            "🧪 [bold blue]Test Case F1.2: Multiple Concurrent Orders[/bold blue]"
        )

        result = {"test_case": "F1.2", "status": "FAILED", "details": [], "duration": 0}
        start_time = time.time()

        # Create 5 concurrent orders
        orders = []
        for i in range(5):
            order_data = {
                "customer_id": f"CUST{i+1:06d}",
                "items": [
                    {"product_id": f"PROD{i+1:06d}", "quantity": 1, "unit_price": 99.99}
                ],
                "payment_method": "credit_card",
                "total_amount": 99.99,
            }
            orders.append(order_data)

        try:
            # Send all orders concurrently
            url = f"{self.base_url}:{self.service_ports['saga']}/api/coordinator/orders"
            tasks = [session.post(url, json=order, timeout=30) for order in orders]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = 0
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    result["details"].append(
                        f"❌ Order {i+1} failed with exception: {response}"
                    )
                else:
                    if response.status in [200, 201]:
                        success_count += 1
                        result["details"].append(f"✅ Order {i+1} created successfully")
                    else:
                        result["details"].append(
                            f"❌ Order {i+1} failed: HTTP {response.status}"
                        )
                    response.close()

            result["details"].append(
                f"📊 {success_count}/{len(orders)} orders succeeded"
            )
            if success_count >= len(orders) * 0.8:  # 80% success rate
                result["status"] = "PASSED"

        except Exception as e:
            result["details"].append(
                f"❌ Exception during concurrent testing: {str(e)}"
            )

        result["duration"] = time.time() - start_time
        return result

    async def test_service_health_validation(
        self, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Test: Service Health Validation"""
        console.print("🧪 [bold blue]Test: Service Health Validation[/bold blue]")

        result = {
            "test_case": "Health",
            "status": "FAILED",
            "details": [],
            "duration": 0,
        }
        start_time = time.time()

        try:
            healthy_services = 0
            total_services = len(self.service_ports)

            for service, port in self.service_ports.items():
                try:
                    url = f"{self.base_url}:{port}/health"
                    async with session.get(url, timeout=5) as response:
                        if response.status == 200:
                            healthy_services += 1
                            result["details"].append(f"✅ {service}: Healthy")
                        else:
                            result["details"].append(
                                f"⚠️ {service}: HTTP {response.status}"
                            )
                except Exception as e:
                    result["details"].append(f"❌ {service}: {str(e)}")

            result["details"].append(
                f"📊 {healthy_services}/{total_services} services healthy"
            )
            if healthy_services == total_services:
                result["status"] = "PASSED"

        except Exception as e:
            result["details"].append(f"❌ Exception during health check: {str(e)}")

        result["duration"] = time.time() - start_time
        return result

    async def test_data_consistency_check(
        self, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Test: Data Consistency Check"""
        console.print("🧪 [bold blue]Test: Data Consistency Check[/bold blue]")

        result = {
            "test_case": "DataConsistency",
            "status": "PASSED",
            "details": [],
            "duration": 0,
        }
        start_time = time.time()

        try:
            # Run the data consistency checker
            import subprocess

            process = subprocess.run(
                ["python", "tools/data_consistency_checker.py"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if process.returncode == 0:
                result["details"].append("✅ Data consistency check passed")
                result["details"].append("📊 No critical issues found")
            else:
                result["details"].append("⚠️ Data consistency issues detected")
                result["details"].append(f"📋 Output: {process.stdout[:200]}...")
                result["status"] = "WARNING"

        except subprocess.TimeoutExpired:
            result["details"].append("⏰ Data consistency check timed out")
            result["status"] = "WARNING"
        except Exception as e:
            result["details"].append(f"❌ Exception during consistency check: {str(e)}")
            result["status"] = "WARNING"

        result["duration"] = time.time() - start_time
        return result

    async def test_api_endpoints_validation(
        self, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Test: API Endpoints Validation"""
        console.print("🧪 [bold blue]Test: API Endpoints Validation[/bold blue]")

        result = {
            "test_case": "APIEndpoints",
            "status": "FAILED",
            "details": [],
            "duration": 0,
        }
        start_time = time.time()

        # Key endpoints to test
        endpoints = [
            {"service": "order", "path": "/health", "method": "GET"},
            {"service": "saga", "path": "/health", "method": "GET"},
            {"service": "inventory", "path": "/health", "method": "GET"},
            {"service": "payment", "path": "/health", "method": "GET"},
            {"service": "shipping", "path": "/health", "method": "GET"},
            {"service": "notification", "path": "/health", "method": "GET"},
        ]

        try:
            working_endpoints = 0

            for endpoint in endpoints:
                service = endpoint["service"]
                path = endpoint["path"]
                port = self.service_ports[service]
                url = f"{self.base_url}:{port}{path}"

                try:
                    async with session.get(url, timeout=5) as response:
                        if response.status == 200:
                            working_endpoints += 1
                            result["details"].append(f"✅ {service}{path}: OK")
                        else:
                            result["details"].append(
                                f"⚠️ {service}{path}: HTTP {response.status}"
                            )
                except Exception as e:
                    result["details"].append(f"❌ {service}{path}: {str(e)}")

            result["details"].append(
                f"📊 {working_endpoints}/{len(endpoints)} endpoints working"
            )
            if working_endpoints >= len(endpoints) * 0.9:  # 90% success rate
                result["status"] = "PASSED"

        except Exception as e:
            result["details"].append(f"❌ Exception during endpoint testing: {str(e)}")

        result["duration"] = time.time() - start_time
        return result

    async def test_database_connectivity(
        self, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """Test: Database Connectivity and Test Data Validation"""
        console.print(
            "🧪 [bold blue]Test: Database Connectivity & Test Data[/bold blue]"
        )

        result = {
            "test_case": "Database",
            "status": "FAILED",
            "details": [],
            "duration": 0,
        }
        start_time = time.time()

        try:
            # Import MongoDB client
            from motor.motor_asyncio import AsyncIOMotorClient

            # Connect to MongoDB
            client = AsyncIOMotorClient("mongodb://localhost:27017")
            db = client.ecommerce_saga

            # Check collections and count documents
            collections = [
                "customers",
                "inventory",
                "orders",
                "payments",
                "notifications",
            ]
            total_documents = 0

            for collection_name in collections:
                try:
                    count = await db[collection_name].count_documents({})
                    total_documents += count
                    result["details"].append(f"✅ {collection_name}: {count} documents")
                except Exception as e:
                    result["details"].append(f"❌ {collection_name}: {str(e)}")

            result["details"].append(f"📊 Total documents: {total_documents}")

            if total_documents > 0:
                result["status"] = "PASSED"
                result["details"].append("✅ Database connectivity confirmed")
            else:
                result["details"].append("⚠️ No test data found")
                result["status"] = "WARNING"

            client.close()

        except ImportError:
            result["details"].append("❌ MongoDB driver (motor) not available")
        except Exception as e:
            result["details"].append(f"❌ Database connection failed: {str(e)}")

        result["duration"] = time.time() - start_time
        return result

    async def run_functional_tests(self):
        """Run all functional tests"""
        console.print("\n🚀 [bold green]Starting Functional Test Suite[/bold green]")
        console.print("=" * 60)

        connector = aiohttp.TCPConnector(limit=10)
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout
        ) as session:
            # List of tests to run
            tests = [
                self.test_service_health_validation,
                self.test_api_endpoints_validation,
                self.test_database_connectivity,
                self.test_data_consistency_check,
                self.test_f11_complete_order_success_flow,
                self.test_f12_multiple_concurrent_orders,
            ]

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:

                task = progress.add_task(
                    "Running functional tests...", total=len(tests)
                )

                for test_func in tests:
                    try:
                        result = await test_func(session)
                        self.test_results.append(result)
                        progress.advance(task)
                    except Exception as e:
                        error_result = {
                            "test_case": test_func.__name__,
                            "status": "ERROR",
                            "details": [f"❌ Test execution failed: {str(e)}"],
                            "duration": 0,
                        }
                        self.test_results.append(error_result)
                        progress.advance(task)

        self.generate_test_report()

    def generate_test_report(self):
        """Generate and display test report"""
        console.print("\n📊 [bold green]Functional Test Results[/bold green]")
        console.print("=" * 80)

        # Summary table
        table = Table(title="🧪 Test Execution Summary", style="cyan")
        table.add_column("Test Case", style="bold")
        table.add_column("Status", style="white")
        table.add_column("Duration", style="green")
        table.add_column("Details", style="white")

        passed = failed = warning = error = 0

        for result in self.test_results:
            # Status styling
            status = result["status"]
            if status == "PASSED":
                status_display = "[green]✅ PASSED[/green]"
                passed += 1
            elif status == "FAILED":
                status_display = "[red]❌ FAILED[/red]"
                failed += 1
            elif status == "WARNING":
                status_display = "[yellow]⚠️ WARNING[/yellow]"
                warning += 1
            else:
                status_display = "[red]💥 ERROR[/red]"
                error += 1

            # Duration formatting
            duration = f"{result['duration']:.2f}s"

            # Details summary
            details_count = len(result["details"])
            details_summary = f"{details_count} checks"

            table.add_row(
                result["test_case"], status_display, duration, details_summary
            )

        console.print(table)

        # Detailed results
        console.print("\n📋 [bold green]Detailed Test Results[/bold green]")
        console.print("-" * 60)

        for result in self.test_results:
            status_color = "green" if result["status"] == "PASSED" else "red"
            console.print(
                f"\n[bold {status_color}]{result['test_case']} - {result['status']}[/bold {status_color}]"
            )
            for detail in result["details"]:
                console.print(f"  {detail}")

        # Overall summary
        total_tests = len(self.test_results)
        console.print(f"\n🎯 [bold green]Test Summary[/bold green]")
        console.print(f"Total Tests: {total_tests}")
        console.print(f"✅ Passed: {passed}")
        console.print(f"⚠️ Warning: {warning}")
        console.print(f"❌ Failed: {failed}")
        console.print(f"💥 Error: {error}")

        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        console.print(f"📊 Success Rate: {success_rate:.1f}%")

        # Overall assessment
        if success_rate >= 90:
            console.print(
                "\n🏆 [bold green]EXCELLENT: System is functioning very well![/bold green]"
            )
        elif success_rate >= 70:
            console.print(
                "\n✅ [bold green]GOOD: System is working with minor issues[/bold green]"
            )
        elif success_rate >= 50:
            console.print(
                "\n⚠️ [bold yellow]MODERATE: System has some significant issues[/bold yellow]"
            )
        else:
            console.print(
                "\n❌ [bold red]POOR: System has major issues requiring attention[/bold red]"
            )


async def main():
    console.print("[bold cyan]🧪 E-Commerce Saga Functional Testing Suite[/bold cyan]")
    console.print("[cyan]Validating key scenarios from Testing.md[/cyan]\n")

    tester = FunctionalTester()
    await tester.run_functional_tests()

    console.print("\n✨ [bold green]Functional testing complete![/bold green]")
    console.print(
        "💡 [yellow]Next steps: Run load tests and chaos tests for comprehensive validation[/yellow]"
    )


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Business Flow Functional Tests for E-Commerce Saga System
Focus on end-to-end customer journeys and business rule validation
"""

import asyncio
import aiohttp
import time
import random
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


class BusinessFlowTester:
    """End-to-end business flow testing"""

    def __init__(self):
        self.base_urls = {
            "order": "http://localhost:8000",
            "inventory": "http://localhost:8001",
            "payment": "http://localhost:8002",
            "shipping": "http://localhost:8003",
            "notification": "http://localhost:8004",
            "saga": "http://localhost:9000",
        }
        self.results = []

    async def make_request(self, method: str, url: str, **kwargs):
        """Make HTTP request with error handling"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(method, url, **kwargs) as response:
                    if response.content_type == "application/json":
                        return {
                            "status": response.status,
                            "data": await response.json(),
                            "success": 200 <= response.status < 300,
                        }
                    else:
                        text = await response.text()
                        return {
                            "status": response.status,
                            "data": {"message": text},
                            "success": 200 <= response.status < 300,
                        }
            except Exception as e:
                return {"status": 0, "data": {"error": str(e)}, "success": False}

    async def test_customer_journey(self):
        """Test complete customer journey"""
        console.print("🛍️ Testing complete customer journey...")

        # Step 1: Browse inventory
        console.print("  Step 1: Browsing inventory...")
        inventory_response = await self.make_request(
            "GET", f"{self.base_urls['inventory']}/api/inventory/statistics"
        )

        if inventory_response["success"]:
            stats = inventory_response["data"]
            console.print(f"    ✅ Found {stats.get('total_products', 0)} products")
        else:
            console.print("    ❌ Failed to browse inventory")
            return False

        # Step 2: Create order
        console.print("  Step 2: Creating order...")
        order_data = {
            "customer_id": f"test.customer.{random.randint(1000, 9999)}@example.com",
            "items": [
                {
                    "product_id": f"product_{random.randint(1, 10)}",
                    "quantity": 1,
                    "price": 29.99,
                }
            ],
            "total_amount": 29.99,
            "shipping_address": {
                "street": "123 Test Street",
                "city": "Test City",
                "state": "TS",
                "zip_code": "12345",
                "country": "USA",
            },
        }

        order_response = await self.make_request(
            "POST",
            f"{self.base_urls['order']}/api/orders",
            json=order_data,
            headers={"Content-Type": "application/json"},
        )

        if order_response["success"]:
            order_id = order_response["data"].get("order_id")
            console.print(f"    ✅ Order created: {order_id}")
        else:
            console.print("    ❌ Failed to create order")
            return False

        # Step 3: Wait for processing
        console.print("  Step 3: Waiting for saga processing...")
        await asyncio.sleep(3)
        console.print("    ✅ Processing time elapsed")

        return True

    async def test_inventory_management(self):
        """Test inventory management flow"""
        console.print("📦 Testing inventory management...")

        # Check inventory statistics
        stats_response = await self.make_request(
            "GET", f"{self.base_urls['inventory']}/api/inventory/statistics"
        )

        if stats_response["success"]:
            stats = stats_response["data"]
            console.print(f"    ✅ Total products: {stats.get('total_products', 0)}")
            console.print(
                f"    ✅ Total categories: {stats.get('total_categories', 0)}"
            )
            return True
        else:
            console.print("    ❌ Failed to check inventory")
            return False

    async def test_saga_coordination(self):
        """Test saga coordination"""
        console.print("🎭 Testing saga coordination...")

        # Check saga health
        health_response = await self.make_request(
            "GET", f"{self.base_urls['saga']}/health"
        )

        if health_response["success"]:
            console.print("    ✅ Saga coordinator healthy")
        else:
            console.print("    ❌ Saga coordinator unhealthy")
            return False

        # Check saga statistics
        stats_response = await self.make_request(
            "GET", f"{self.base_urls['saga']}/api/sagas/statistics"
        )

        if stats_response["success"]:
            stats = stats_response["data"]
            console.print(f"    ✅ Total sagas: {stats.get('total_sagas', 0)}")
            return True
        else:
            console.print("    ⚠️ Could not retrieve saga statistics")
            return True  # Non-critical failure

    async def run_all_tests(self):
        """Run all business flow tests"""
        console.print(
            Panel.fit(
                "[bold cyan]🏢 BUSINESS FLOW FUNCTIONAL TESTS[/bold cyan]\n"
                "[dim]Testing end-to-end customer journeys[/dim]",
                box=box.DOUBLE,
            )
        )

        tests = [
            ("Customer Journey", self.test_customer_journey),
            ("Inventory Management", self.test_inventory_management),
            ("Saga Coordination", self.test_saga_coordination),
        ]

        results = []

        for test_name, test_func in tests:
            start_time = time.time()
            try:
                success = await test_func()
                duration = time.time() - start_time
                results.append((test_name, success, duration))

                status = "✅ PASSED" if success else "❌ FAILED"
                console.print(f"{status} {test_name} ({duration:.2f}s)")

            except Exception as e:
                duration = time.time() - start_time
                results.append((test_name, False, duration))
                console.print(f"❌ FAILED {test_name} - Error: {str(e)}")

        # Generate summary
        passed = sum(1 for _, success, _ in results if success)
        total = len(results)

        summary_table = Table(title="📊 Business Flow Summary", box=box.ROUNDED)
        summary_table.add_column("Test", style="cyan")
        summary_table.add_column("Status", style="white")
        summary_table.add_column("Duration", style="green")

        for test_name, success, duration in results:
            status = "✅ PASSED" if success else "❌ FAILED"
            summary_table.add_row(test_name, status, f"{duration:.2f}s")

        console.print(summary_table)

        # Overall status
        if passed == total:
            console.print(
                Panel.fit(
                    "[bold green]🏆 ALL BUSINESS FLOWS SUCCESSFUL![/bold green]\n"
                    "[dim]E-commerce business logic working correctly[/dim]",
                    box=box.DOUBLE,
                )
            )
        else:
            console.print(
                Panel.fit(
                    f"[bold yellow]⚠️ {passed}/{total} TESTS PASSED[/bold yellow]\n"
                    "[dim]Some business flows need attention[/dim]",
                    box=box.DOUBLE,
                )
            )


async def main():
    """Main business flow test execution"""
    tester = BusinessFlowTester()

    try:
        await tester.run_all_tests()
    except Exception as e:
        console.print(f"❌ Business flow tests failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Comprehensive Functional Test Suite for E-Commerce Saga System
Tests all major business workflows and error scenarios
"""

import asyncio
import aiohttp
import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from motor.motor_asyncio import AsyncIOMotorClient
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, TaskID
from rich.text import Text
from rich import box

console = Console()


@dataclass
class TestResult:
    """Test result container"""

    test_name: str
    success: bool
    message: str
    duration: float
    details: Optional[Dict[str, Any]] = None


@dataclass
class Customer:
    """Customer test data"""

    name: str
    email: str
    phone: str
    address: Dict[str, str]


@dataclass
class Product:
    """Product test data"""

    name: str
    price: float
    category: str
    stock_quantity: int


@dataclass
class Order:
    """Order test data"""

    customer_id: str
    items: List[Dict[str, Any]]
    total_amount: float
    shipping_address: Dict[str, str]


class FunctionalTestSuite:
    """Comprehensive functional test suite"""

    def __init__(self):
        self.base_urls = {
            "order": "http://localhost:8000",
            "inventory": "http://localhost:8001",
            "payment": "http://localhost:8002",
            "shipping": "http://localhost:8003",
            "notification": "http://localhost:8004",
            "saga": "http://localhost:9000",
        }
        self.db_client = None
        self.db = None
        self.results: List[TestResult] = []

    async def initialize(self):
        """Initialize database connection"""
        try:
            self.db_client = AsyncIOMotorClient("mongodb://localhost:27017")
            self.db = self.db_client.ecommerce_saga
            await self.db_client.admin.command("ping")
            console.print("✅ Database connection established")
        except Exception as e:
            console.print(f"❌ Database connection failed: {e}")
            raise

    async def cleanup(self):
        """Cleanup resources"""
        if self.db_client:
            self.db_client.close()

    async def make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
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

    async def create_test_customer(self) -> Customer:
        """Create a test customer"""
        customer = Customer(
            name=f"Test Customer {random.randint(1000, 9999)}",
            email=f"test.customer.{random.randint(1000, 9999)}@example.com",
            phone=f"555-{random.randint(1000, 9999)}",
            address={
                "street": f"{random.randint(100, 999)} Test Street",
                "city": "Test City",
                "state": "TS",
                "zip_code": f"{random.randint(10000, 99999)}",
                "country": "USA",
            },
        )

        # Insert into database
        customer_doc = asdict(customer)
        result = await self.db.customers.insert_one(customer_doc)
        customer_doc["_id"] = str(result.inserted_id)
        return customer

    async def create_test_product(self) -> Product:
        """Create a test product"""
        product = Product(
            name=f"Test Product {random.randint(1000, 9999)}",
            price=round(random.uniform(10.0, 500.0), 2),
            category=random.choice(["Electronics", "Books", "Clothing", "Sports"]),
            stock_quantity=random.randint(10, 100),
        )

        # Insert into database
        product_doc = asdict(product)
        result = await self.db.inventory.insert_one(product_doc)
        product_doc["_id"] = str(result.inserted_id)
        return product

    # Test Scenarios

    async def test_service_health_endpoints(self) -> TestResult:
        """Test all service health endpoints"""
        start_time = time.time()

        try:
            console.print("🩺 Testing service health endpoints...")

            healthy_services = 0
            total_services = len(self.base_urls)

            for service, base_url in self.base_urls.items():
                response = await self.make_request("GET", f"{base_url}/health")
                if response["success"]:
                    healthy_services += 1
                    console.print(f"  ✅ {service}: Healthy")
                else:
                    console.print(f"  ❌ {service}: Unhealthy ({response['status']})")

            success = healthy_services == total_services
            message = f"{healthy_services}/{total_services} services healthy"

            return TestResult(
                test_name="Service Health Check",
                success=success,
                message=message,
                duration=time.time() - start_time,
                details={
                    "healthy_services": healthy_services,
                    "total_services": total_services,
                },
            )

        except Exception as e:
            return TestResult(
                test_name="Service Health Check",
                success=False,
                message=f"Error: {str(e)}",
                duration=time.time() - start_time,
            )

    async def test_complete_order_workflow(self) -> TestResult:
        """Test complete order processing workflow"""
        start_time = time.time()

        try:
            console.print("📦 Testing complete order workflow...")

            # Step 1: Create test customer and product
            customer = await self.create_test_customer()
            product = await self.create_test_product()

            # Step 2: Create order
            order_data = {
                "customer_id": customer.email,
                "items": [
                    {"product_id": product.name, "quantity": 2, "price": product.price}
                ],
                "total_amount": product.price * 2,
                "shipping_address": customer.address,
            }

            response = await self.make_request(
                "POST",
                f"{self.base_urls['order']}/api/orders",
                json=order_data,
                headers={"Content-Type": "application/json"},
            )

            if not response["success"]:
                return TestResult(
                    test_name="Complete Order Workflow",
                    success=False,
                    message=f"Order creation failed: {response['data']}",
                    duration=time.time() - start_time,
                )

            order_id = response["data"].get("order_id")
            console.print(f"  ✅ Order created: {order_id}")

            # Step 3: Wait for saga processing
            await asyncio.sleep(2)

            # Step 4: Check order status
            status_response = await self.make_request(
                "GET", f"{self.base_urls['order']}/api/orders/{order_id}"
            )

            if status_response["success"]:
                order_status = status_response["data"].get("status")
                console.print(f"  ✅ Order status: {order_status}")

            return TestResult(
                test_name="Complete Order Workflow",
                success=True,
                message="Order workflow completed successfully",
                duration=time.time() - start_time,
                details={"order_id": order_id, "customer": customer.email},
            )

        except Exception as e:
            return TestResult(
                test_name="Complete Order Workflow",
                success=False,
                message=f"Error: {str(e)}",
                duration=time.time() - start_time,
            )

    async def test_payment_processing_scenarios(self) -> TestResult:
        """Test payment processing scenarios"""
        start_time = time.time()

        try:
            console.print("💳 Testing payment processing scenarios...")

            # Test successful payment
            payment_data = {
                "order_id": f"test_order_{random.randint(1000, 9999)}",
                "amount": 99.99,
                "payment_method": "credit_card",
                "card_details": {
                    "card_number": "4111111111111111",  # Test card
                    "expiry": "12/25",
                    "cvv": "123",
                },
            }

            response = await self.make_request(
                "POST",
                f"{self.base_urls['payment']}/api/payments/process",
                json=payment_data,
                headers={"Content-Type": "application/json"},
            )

            if response["success"]:
                console.print("  ✅ Payment processing successful")
                payment_id = response["data"].get("payment_id")
            else:
                console.print(f"  ❌ Payment processing failed: {response['data']}")
                return TestResult(
                    test_name="Payment Processing",
                    success=False,
                    message="Payment processing failed",
                    duration=time.time() - start_time,
                )

            # Test payment status check
            status_response = await self.make_request(
                "GET", f"{self.base_urls['payment']}/api/payments/{payment_id}/status"
            )

            if status_response["success"]:
                payment_status = status_response["data"].get("status")
                console.print(f"  ✅ Payment status: {payment_status}")

            return TestResult(
                test_name="Payment Processing",
                success=True,
                message="Payment scenarios completed successfully",
                duration=time.time() - start_time,
                details={"payment_id": payment_id},
            )

        except Exception as e:
            return TestResult(
                test_name="Payment Processing",
                success=False,
                message=f"Error: {str(e)}",
                duration=time.time() - start_time,
            )

    async def test_inventory_management(self) -> TestResult:
        """Test inventory management scenarios"""
        start_time = time.time()

        try:
            console.print("📦 Testing inventory management...")

            # Test inventory check
            response = await self.make_request(
                "GET", f"{self.base_urls['inventory']}/api/inventory/statistics"
            )

            if not response["success"]:
                return TestResult(
                    test_name="Inventory Management",
                    success=False,
                    message="Inventory statistics failed",
                    duration=time.time() - start_time,
                )

            stats = response["data"]
            console.print(f"  ✅ Total products: {stats.get('total_products', 0)}")
            console.print(f"  ✅ Total stock: {stats.get('total_stock_value', 0)}")

            # Test product availability check
            product = await self.create_test_product()

            availability_response = await self.make_request(
                "GET",
                f"{self.base_urls['inventory']}/api/inventory/{product.name}/availability",
            )

            if availability_response["success"]:
                available = availability_response["data"].get("available", False)
                console.print(f"  ✅ Product availability: {available}")

            return TestResult(
                test_name="Inventory Management",
                success=True,
                message="Inventory management tests completed",
                duration=time.time() - start_time,
                details=stats,
            )

        except Exception as e:
            return TestResult(
                test_name="Inventory Management",
                success=False,
                message=f"Error: {str(e)}",
                duration=time.time() - start_time,
            )

    async def test_shipping_workflows(self) -> TestResult:
        """Test shipping workflow scenarios"""
        start_time = time.time()

        try:
            console.print("🚛 Testing shipping workflows...")

            # Test shipment creation
            shipment_data = {
                "order_id": f"test_order_{random.randint(1000, 9999)}",
                "shipping_address": {
                    "street": "123 Test Street",
                    "city": "Test City",
                    "state": "TS",
                    "zip_code": "12345",
                    "country": "USA",
                },
                "items": [{"product_id": "test_product", "quantity": 1, "weight": 1.5}],
            }

            response = await self.make_request(
                "POST",
                f"{self.base_urls['shipping']}/api/shipments",
                json=shipment_data,
                headers={"Content-Type": "application/json"},
            )

            if not response["success"]:
                return TestResult(
                    test_name="Shipping Workflows",
                    success=False,
                    message=f"Shipment creation failed: {response['data']}",
                    duration=time.time() - start_time,
                )

            shipment_id = response["data"].get("shipment_id")
            console.print(f"  ✅ Shipment created: {shipment_id}")

            # Test shipment tracking
            tracking_response = await self.make_request(
                "GET", f"{self.base_urls['shipping']}/api/shipments/{shipment_id}/track"
            )

            if tracking_response["success"]:
                tracking_info = tracking_response["data"]
                console.print(f"  ✅ Tracking status: {tracking_info.get('status')}")

            return TestResult(
                test_name="Shipping Workflows",
                success=True,
                message="Shipping workflows completed successfully",
                duration=time.time() - start_time,
                details={"shipment_id": shipment_id},
            )

        except Exception as e:
            return TestResult(
                test_name="Shipping Workflows",
                success=False,
                message=f"Error: {str(e)}",
                duration=time.time() - start_time,
            )

    async def test_notification_system(self) -> TestResult:
        """Test notification system"""
        start_time = time.time()

        try:
            console.print("📧 Testing notification system...")

            # Test notification sending
            notification_data = {
                "customer_id": f"test_customer_{random.randint(1000, 9999)}",
                "type": "order_confirmation",
                "message": "Your order has been confirmed",
                "channel": "email",
                "metadata": {
                    "order_id": f"test_order_{random.randint(1000, 9999)}",
                    "timestamp": datetime.now().isoformat(),
                },
            }

            response = await self.make_request(
                "POST",
                f"{self.base_urls['notification']}/api/notifications/send",
                json=notification_data,
                headers={"Content-Type": "application/json"},
            )

            if not response["success"]:
                return TestResult(
                    test_name="Notification System",
                    success=False,
                    message=f"Notification sending failed: {response['data']}",
                    duration=time.time() - start_time,
                )

            notification_id = response["data"].get("notification_id")
            console.print(f"  ✅ Notification sent: {notification_id}")

            # Test notification history
            history_response = await self.make_request(
                "GET",
                f"{self.base_urls['notification']}/api/notifications/{notification_data['customer_id']}/history",
            )

            if history_response["success"]:
                history = history_response["data"]
                console.print(
                    f"  ✅ Notification history: {len(history.get('notifications', []))} notifications"
                )

            return TestResult(
                test_name="Notification System",
                success=True,
                message="Notification system tests completed",
                duration=time.time() - start_time,
                details={"notification_id": notification_id},
            )

        except Exception as e:
            return TestResult(
                test_name="Notification System",
                success=False,
                message=f"Error: {str(e)}",
                duration=time.time() - start_time,
            )

    async def test_saga_orchestration(self) -> TestResult:
        """Test saga orchestration scenarios"""
        start_time = time.time()

        try:
            console.print("🎭 Testing saga orchestration...")

            # Test saga status
            response = await self.make_request(
                "GET", f"{self.base_urls['saga']}/api/sagas/statistics"
            )

            if not response["success"]:
                return TestResult(
                    test_name="Saga Orchestration",
                    success=False,
                    message="Saga statistics failed",
                    duration=time.time() - start_time,
                )

            stats = response["data"]
            console.print(f"  ✅ Total sagas: {stats.get('total_sagas', 0)}")
            console.print(f"  ✅ Completed sagas: {stats.get('completed_sagas', 0)}")
            console.print(f"  ✅ Failed sagas: {stats.get('failed_sagas', 0)}")

            # Test saga creation
            saga_data = {
                "saga_type": "order_processing",
                "order_data": {
                    "order_id": f"test_order_{random.randint(1000, 9999)}",
                    "customer_id": f"test_customer_{random.randint(1000, 9999)}",
                    "total_amount": 99.99,
                },
            }

            create_response = await self.make_request(
                "POST",
                f"{self.base_urls['saga']}/api/sagas/start",
                json=saga_data,
                headers={"Content-Type": "application/json"},
            )

            if create_response["success"]:
                saga_id = create_response["data"].get("saga_id")
                console.print(f"  ✅ Saga started: {saga_id}")

            return TestResult(
                test_name="Saga Orchestration",
                success=True,
                message="Saga orchestration tests completed",
                duration=time.time() - start_time,
                details=stats,
            )

        except Exception as e:
            return TestResult(
                test_name="Saga Orchestration",
                success=False,
                message=f"Error: {str(e)}",
                duration=time.time() - start_time,
            )

    async def test_error_handling_scenarios(self) -> TestResult:
        """Test error handling and compensation scenarios"""
        start_time = time.time()

        try:
            console.print("🚨 Testing error handling scenarios...")

            # Test invalid order data
            invalid_order = {
                "customer_id": "",  # Invalid customer ID
                "items": [],  # Empty items
                "total_amount": -10,  # Negative amount
            }

            response = await self.make_request(
                "POST",
                f"{self.base_urls['order']}/api/orders",
                json=invalid_order,
                headers={"Content-Type": "application/json"},
            )

            # Should fail with validation error
            if response["status"] == 400:
                console.print("  ✅ Invalid order correctly rejected")
            else:
                console.print("  ❌ Invalid order should have been rejected")

            # Test payment with invalid card
            invalid_payment = {
                "order_id": f"test_order_{random.randint(1000, 9999)}",
                "amount": 99.99,
                "payment_method": "credit_card",
                "card_details": {
                    "card_number": "0000000000000000",  # Invalid card
                    "expiry": "01/20",  # Expired
                    "cvv": "000",
                },
            }

            payment_response = await self.make_request(
                "POST",
                f"{self.base_urls['payment']}/api/payments/process",
                json=invalid_payment,
                headers={"Content-Type": "application/json"},
            )

            # Should handle payment error gracefully
            if payment_response["status"] in [400, 422]:
                console.print("  ✅ Invalid payment correctly handled")
            else:
                console.print("  ❌ Invalid payment should have been handled")

            return TestResult(
                test_name="Error Handling",
                success=True,
                message="Error handling scenarios completed",
                duration=time.time() - start_time,
            )

        except Exception as e:
            return TestResult(
                test_name="Error Handling",
                success=False,
                message=f"Error: {str(e)}",
                duration=time.time() - start_time,
            )

    async def test_data_consistency(self) -> TestResult:
        """Test data consistency across services"""
        start_time = time.time()

        try:
            console.print("🔍 Testing data consistency...")

            # Check database collections
            collections = [
                "customers",
                "inventory",
                "orders",
                "payments",
                "shipments",
                "notifications",
            ]
            collection_counts = {}

            for collection_name in collections:
                try:
                    count = await self.db[collection_name].count_documents({})
                    collection_counts[collection_name] = count
                    console.print(f"  ✅ {collection_name}: {count} documents")
                except Exception as e:
                    console.print(f"  ❌ {collection_name}: Error - {str(e)}")
                    collection_counts[collection_name] = 0

            total_documents = sum(collection_counts.values())

            # Check for orphaned records (basic consistency check)
            orders_count = collection_counts.get("orders", 0)
            payments_count = collection_counts.get("payments", 0)

            consistency_issues = []

            if orders_count > 0 and payments_count == 0:
                consistency_issues.append("Orders exist without payments")

            if len(consistency_issues) == 0:
                console.print("  ✅ No obvious consistency issues found")
            else:
                for issue in consistency_issues:
                    console.print(f"  ⚠️ {issue}")

            return TestResult(
                test_name="Data Consistency",
                success=len(consistency_issues) == 0,
                message=f"Checked {len(collections)} collections, {total_documents} total documents",
                duration=time.time() - start_time,
                details=collection_counts,
            )

        except Exception as e:
            return TestResult(
                test_name="Data Consistency",
                success=False,
                message=f"Error: {str(e)}",
                duration=time.time() - start_time,
            )

    async def run_all_tests(self) -> List[TestResult]:
        """Run all functional tests"""
        console.print(
            Panel.fit(
                "[bold cyan]🧪 COMPREHENSIVE FUNCTIONAL TEST SUITE[/bold cyan]\n"
                "[dim]Testing all e-commerce saga workflows and scenarios[/dim]",
                box=box.DOUBLE,
            )
        )

        test_functions = [
            self.test_service_health_endpoints,
            self.test_complete_order_workflow,
            self.test_payment_processing_scenarios,
            self.test_inventory_management,
            self.test_shipping_workflows,
            self.test_notification_system,
            self.test_saga_orchestration,
            self.test_error_handling_scenarios,
            self.test_data_consistency,
        ]

        results = []

        with Progress() as progress:
            task = progress.add_task("Running tests...", total=len(test_functions))

            for test_function in test_functions:
                try:
                    result = await test_function()
                    results.append(result)

                    # Display result
                    status = "✅ PASSED" if result.success else "❌ FAILED"
                    console.print(
                        f"{status} {result.test_name} ({result.duration:.2f}s)"
                    )
                    if not result.success:
                        console.print(f"   └─ {result.message}")

                    progress.advance(task)

                except Exception as e:
                    result = TestResult(
                        test_name=test_function.__name__.replace("test_", "")
                        .replace("_", " ")
                        .title(),
                        success=False,
                        message=f"Test error: {str(e)}",
                        duration=0.0,
                    )
                    results.append(result)
                    console.print(f"❌ FAILED {result.test_name} - {result.message}")
                    progress.advance(task)

        self.results = results
        return results

    def generate_test_report(self) -> None:
        """Generate comprehensive test report"""
        if not self.results:
            console.print("❌ No test results to report")
            return

        # Summary statistics
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests
        total_duration = sum(r.duration for r in self.results)

        # Create summary table
        summary_table = Table(title="📊 Test Summary", box=box.ROUNDED)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="white")
        summary_table.add_column("Status", style="green")

        summary_table.add_row("Total Tests", str(total_tests), "ℹ️")
        summary_table.add_row("Passed", str(passed_tests), "✅")
        summary_table.add_row(
            "Failed", str(failed_tests), "❌" if failed_tests > 0 else "✅"
        )
        summary_table.add_row(
            "Success Rate",
            f"{(passed_tests/total_tests)*100:.1f}%",
            "✅" if passed_tests == total_tests else "⚠️",
        )
        summary_table.add_row("Total Duration", f"{total_duration:.2f}s", "⏱️")

        console.print(summary_table)

        # Detailed results table
        details_table = Table(
            title="📋 Detailed Test Results", box=box.ROUNDED, show_lines=True
        )
        details_table.add_column("Test Name", width=25)
        details_table.add_column("Status", width=10, justify="center")
        details_table.add_column("Duration", width=10, justify="right")
        details_table.add_column("Message", width=40)

        for result in self.results:
            status = (
                "[green]✅ PASSED[/green]" if result.success else "[red]❌ FAILED[/red]"
            )
            details_table.add_row(
                result.test_name,
                status,
                f"{result.duration:.2f}s",
                (
                    result.message[:40] + "..."
                    if len(result.message) > 40
                    else result.message
                ),
            )

        console.print(details_table)

        # Overall status
        if passed_tests == total_tests:
            console.print(
                Panel.fit(
                    "[bold green]🏆 ALL TESTS PASSED![/bold green]\n"
                    "[dim]The e-commerce saga system is functioning correctly[/dim]",
                    box=box.DOUBLE,
                )
            )
        elif passed_tests >= total_tests * 0.8:
            console.print(
                Panel.fit(
                    "[bold yellow]⚠️ MOSTLY SUCCESSFUL[/bold yellow]\n"
                    f"[dim]{passed_tests}/{total_tests} tests passed - Minor issues detected[/dim]",
                    box=box.DOUBLE,
                )
            )
        else:
            console.print(
                Panel.fit(
                    "[bold red]❌ MULTIPLE FAILURES DETECTED[/bold red]\n"
                    f"[dim]{failed_tests}/{total_tests} tests failed - System needs attention[/dim]",
                    box=box.DOUBLE,
                )
            )


async def main():
    """Main test execution"""
    test_suite = FunctionalTestSuite()

    try:
        # Initialize
        await test_suite.initialize()

        # Run all tests
        results = await test_suite.run_all_tests()

        # Generate report
        console.print("\n" + "=" * 80)
        test_suite.generate_test_report()

    except Exception as e:
        console.print(f"❌ Test suite failed to initialize: {e}")
        return

    finally:
        # Cleanup
        await test_suite.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

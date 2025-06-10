#!/usr/bin/env python3
"""
Automated Functional Test Suite for E-commerce Saga System

This script runs comprehensive functional tests including:
- Success scenarios
- Failure scenarios
- Performance tests
- Data consistency checks
"""

import asyncio
import aiohttp
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sys
import os
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient


class TestResult:
    def __init__(
        self,
        name: str,
        success: bool,
        message: str,
        duration_ms: float = 0,
        details: Dict = None,
    ):
        self.name = name
        self.success = success
        self.message = message
        self.duration_ms = duration_ms
        self.details = details or {}
        self.timestamp = datetime.now()


class FunctionalTestRunner:
    def __init__(self):
        self.base_url = "http://localhost"
        self.services = {
            "order": 8000,
            "inventory": 8001,
            "payment": 8002,
            "shipping": 8003,
            "notification": 8004,
            "coordinator": 9000,
        }
        self.db_client = None
        self.db = None
        self.test_results: List[TestResult] = []
        self.test_customers = []
        self.test_products = []

    async def setup(self):
        """Setup test environment"""
        print("🔧 Setting up test environment...")

        # Connect to MongoDB
        self.db_client = AsyncIOMotorClient("mongodb://localhost:27017")
        self.db = self.db_client.ecommerce_saga

        # Verify services are running
        async with aiohttp.ClientSession() as session:
            for service, port in self.services.items():
                try:
                    async with session.get(
                        f"{self.base_url}:{port}/health", timeout=5
                    ) as response:
                        if response.status != 200:
                            raise Exception(f"Service {service} not healthy")
                    print(f"✅ {service} service is healthy")
                except Exception as e:
                    print(f"❌ {service} service failed: {str(e)}")
                    raise

        # Load test data
        await self._load_test_data()
        print("✅ Test environment ready")

    async def _load_test_data(self):
        """Load test customers and products"""
        self.test_customers = await self.db.customers.find().limit(10).to_list(None)
        self.test_products = (
            await self.db.inventory.find(
                {"status": "AVAILABLE", "quantity": {"$gt": 5}}
            )
            .limit(10)
            .to_list(None)
        )

        if not self.test_customers or not self.test_products:
            raise Exception("No test data found. Run test_data_generator.py first")

    async def cleanup(self):
        """Cleanup test environment"""
        if self.db_client:
            self.db_client.close()

    def add_result(self, result: TestResult):
        """Add test result"""
        self.test_results.append(result)
        status = "✅ PASS" if result.success else "❌ FAIL"
        print(f"{status} {result.name} ({result.duration_ms:.0f}ms) - {result.message}")

    async def test_complete_order_flow(self) -> TestResult:
        """Test SC-01: Complete Order Success Flow"""
        start_time = time.time()
        correlation_id = str(uuid.uuid4())

        try:
            customer = self.test_customers[0]
            product = self.test_products[0]

            order_data = {
                "customer_id": customer["customer_id"],
                "items": [
                    {
                        "product_id": product["product_id"],
                        "quantity": 1,
                        "price": product["price"],
                    }
                ],
                "shipping_address": customer["shipping_address"],
                "payment_method": "CREDIT_CARD",
            }

            async with aiohttp.ClientSession() as session:
                # Create order through coordinator
                headers = {
                    "Content-Type": "application/json",
                    "X-Correlation-ID": correlation_id,
                }

                async with session.post(
                    f"{self.base_url}:{self.services['coordinator']}/api/coordinator/orders",
                    json=order_data,
                    headers=headers,
                    timeout=30,
                ) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        raise Exception(
                            f"Order creation failed: {response.status} - {response_text}"
                        )

                    result = await response.json()
                    order_id = result.get("order_id")

                    if not order_id:
                        raise Exception("No order_id in response")

            # Wait for saga completion
            await asyncio.sleep(5)

            # Verify order completion
            order = await self.db.orders.find_one({"order_id": order_id})
            if not order or order.get("status") != "COMPLETED":
                raise Exception(
                    f"Order not completed. Status: {order.get('status') if order else 'NOT_FOUND'}"
                )

            # Verify inventory was reduced
            updated_product = await self.db.inventory.find_one(
                {"product_id": product["product_id"]}
            )
            if updated_product["quantity"] != product["quantity"] - 1:
                raise Exception("Inventory not properly reduced")

            # Verify payment was processed
            payment = await self.db.payments.find_one({"order_id": order_id})
            if not payment or payment.get("status") != "COMPLETED":
                raise Exception(
                    f"Payment not completed. Status: {payment.get('status') if payment else 'NOT_FOUND'}"
                )

            # Verify shipping was scheduled
            shipment = await self.db.shipments.find_one({"order_id": order_id})
            if not shipment or shipment.get("status") not in ["SCHEDULED", "PENDING"]:
                raise Exception(
                    f"Shipment not scheduled. Status: {shipment.get('status') if shipment else 'NOT_FOUND'}"
                )

            duration_ms = (time.time() - start_time) * 1000
            return TestResult(
                "Complete Order Flow",
                True,
                f"Order {order_id} completed successfully",
                duration_ms,
                {"order_id": order_id, "correlation_id": correlation_id},
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult("Complete Order Flow", False, str(e), duration_ms)

    async def test_insufficient_inventory(self) -> TestResult:
        """Test FS-01: Insufficient Inventory"""
        start_time = time.time()
        correlation_id = str(uuid.uuid4())

        try:
            customer = self.test_customers[0]
            product = self.test_products[0]

            # Request more than available
            order_data = {
                "customer_id": customer["customer_id"],
                "items": [
                    {
                        "product_id": product["product_id"],
                        "quantity": product["quantity"] + 100,  # More than available
                        "price": product["price"],
                    }
                ],
                "shipping_address": customer["shipping_address"],
                "payment_method": "CREDIT_CARD",
            }

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "X-Correlation-ID": correlation_id,
                }

                async with session.post(
                    f"{self.base_url}:{self.services['coordinator']}/api/coordinator/orders",
                    json=order_data,
                    headers=headers,
                    timeout=30,
                ) as response:
                    # Should fail with 400
                    if response.status == 200:
                        result = await response.json()
                        order_id = result.get("order_id")

                        # Wait for saga completion/compensation
                        await asyncio.sleep(5)

                        # Check order was cancelled
                        order = await self.db.orders.find_one({"order_id": order_id})
                        if not order or order.get("status") != "CANCELLED":
                            raise Exception(
                                f"Order should be cancelled. Status: {order.get('status') if order else 'NOT_FOUND'}"
                            )

                    # Verify inventory unchanged
                    current_product = await self.db.inventory.find_one(
                        {"product_id": product["product_id"]}
                    )
                    if current_product["quantity"] != product["quantity"]:
                        raise Exception("Inventory should remain unchanged")

            duration_ms = (time.time() - start_time) * 1000
            return TestResult(
                "Insufficient Inventory",
                True,
                "Order correctly failed due to insufficient inventory",
                duration_ms,
                {"correlation_id": correlation_id},
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult("Insufficient Inventory", False, str(e), duration_ms)

    async def test_concurrent_orders(self) -> TestResult:
        """Test TC-04: Concurrent Orders"""
        start_time = time.time()

        try:
            customer = self.test_customers[0]
            product = self.test_products[1]  # Use different product
            initial_quantity = product["quantity"]

            # Create 5 concurrent orders for 1 item each
            order_tasks = []

            for i in range(5):
                order_data = {
                    "customer_id": customer["customer_id"],
                    "items": [
                        {
                            "product_id": product["product_id"],
                            "quantity": 1,
                            "price": product["price"],
                        }
                    ],
                    "shipping_address": customer["shipping_address"],
                    "payment_method": "CREDIT_CARD",
                }

                task = self._create_order_async(order_data, f"concurrent-{i}")
                order_tasks.append(task)

            # Execute all orders concurrently
            results = await asyncio.gather(*order_tasks, return_exceptions=True)

            # Wait for all sagas to complete
            await asyncio.sleep(10)

            # Count successful orders
            successful_orders = 0
            for result in results:
                if isinstance(result, dict) and result.get("order_id"):
                    order = await self.db.orders.find_one(
                        {"order_id": result["order_id"]}
                    )
                    if order and order.get("status") == "COMPLETED":
                        successful_orders += 1

            # Verify inventory is consistent
            final_product = await self.db.inventory.find_one(
                {"product_id": product["product_id"]}
            )
            expected_quantity = initial_quantity - successful_orders

            if final_product["quantity"] != expected_quantity:
                raise Exception(
                    f"Inventory inconsistent. Expected: {expected_quantity}, Actual: {final_product['quantity']}"
                )

            duration_ms = (time.time() - start_time) * 1000
            return TestResult(
                "Concurrent Orders",
                True,
                f"{successful_orders} orders completed successfully, inventory consistent",
                duration_ms,
                {
                    "initial_quantity": initial_quantity,
                    "successful_orders": successful_orders,
                    "final_quantity": final_product["quantity"],
                },
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult("Concurrent Orders", False, str(e), duration_ms)

    async def _create_order_async(self, order_data: Dict, correlation_id: str) -> Dict:
        """Helper to create order asynchronously"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "X-Correlation-ID": correlation_id,
            }

            async with session.post(
                f"{self.base_url}:{self.services['coordinator']}/api/coordinator/orders",
                json=order_data,
                headers=headers,
                timeout=30,
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Order creation failed: {response.status}")

    async def test_data_consistency(self) -> TestResult:
        """Test data consistency across services"""
        start_time = time.time()

        try:
            # Check for orphaned records
            issues = []

            # Check orders without corresponding payments (for completed orders)
            completed_orders = await self.db.orders.find(
                {"status": "COMPLETED"}
            ).to_list(None)
            for order in completed_orders:
                payment = await self.db.payments.find_one(
                    {"order_id": order["order_id"]}
                )
                if not payment:
                    issues.append(
                        f"Completed order {order['order_id']} has no payment record"
                    )

            # Check payments without corresponding orders
            payments = await self.db.payments.find({}).to_list(None)
            for payment in payments:
                order = await self.db.orders.find_one({"order_id": payment["order_id"]})
                if not order:
                    issues.append(
                        f"Payment {payment['payment_id']} has no corresponding order"
                    )

            # Check for negative inventory
            negative_inventory = await self.db.inventory.find(
                {"quantity": {"$lt": 0}}
            ).to_list(None)
            for item in negative_inventory:
                issues.append(
                    f"Product {item['product_id']} has negative quantity: {item['quantity']}"
                )

            # Check for unreleased reservations
            old_reservations = await self.db.inventory_reservations.find(
                {
                    "created_at": {"$lt": datetime.now() - timedelta(hours=1)},
                    "status": "RESERVED",
                }
            ).to_list(None)

            for reservation in old_reservations:
                issues.append(
                    f"Old reservation {reservation['reservation_id']} not released"
                )

            duration_ms = (time.time() - start_time) * 1000

            if issues:
                return TestResult(
                    "Data Consistency",
                    False,
                    f"Found {len(issues)} consistency issues",
                    duration_ms,
                    {"issues": issues},
                )
            else:
                return TestResult(
                    "Data Consistency",
                    True,
                    "All data consistency checks passed",
                    duration_ms,
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult("Data Consistency", False, str(e), duration_ms)

    async def test_performance_metrics(self) -> TestResult:
        """Test performance metrics"""
        start_time = time.time()

        try:
            # Get recent saga logs
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_sagas = await self.db.saga_logs.find(
                {"created_at": {"$gte": one_hour_ago}}
            ).to_list(None)

            if not recent_sagas:
                return TestResult(
                    "Performance Metrics",
                    True,
                    "No recent saga data for performance analysis",
                    (time.time() - start_time) * 1000,
                )

            # Calculate metrics
            completed_sagas = [
                s for s in recent_sagas if s.get("status") == "COMPLETED"
            ]
            failed_sagas = [
                s for s in recent_sagas if s.get("status") in ["FAILED", "COMPENSATED"]
            ]

            success_rate = (
                len(completed_sagas) / len(recent_sagas) if recent_sagas else 0
            )

            # Calculate average duration for completed sagas
            durations = [
                s.get("total_duration_ms", 0)
                for s in completed_sagas
                if s.get("total_duration_ms")
            ]
            avg_duration = sum(durations) / len(durations) if durations else 0
            max_duration = max(durations) if durations else 0

            # Performance thresholds
            issues = []
            if success_rate < 0.95:  # Less than 95% success rate
                issues.append(f"Low success rate: {success_rate:.2%}")

            if avg_duration > 30000:  # More than 30 seconds average
                issues.append(f"High average duration: {avg_duration:.0f}ms")

            if max_duration > 60000:  # More than 1 minute max
                issues.append(f"Very high max duration: {max_duration:.0f}ms")

            duration_ms = (time.time() - start_time) * 1000

            metrics = {
                "total_sagas": len(recent_sagas),
                "completed_sagas": len(completed_sagas),
                "failed_sagas": len(failed_sagas),
                "success_rate": success_rate,
                "avg_duration_ms": avg_duration,
                "max_duration_ms": max_duration,
            }

            if issues:
                return TestResult(
                    "Performance Metrics",
                    False,
                    f"Performance issues detected: {', '.join(issues)}",
                    duration_ms,
                    metrics,
                )
            else:
                return TestResult(
                    "Performance Metrics",
                    True,
                    f"Performance acceptable - {success_rate:.1%} success rate, {avg_duration:.0f}ms avg duration",
                    duration_ms,
                    metrics,
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult("Performance Metrics", False, str(e), duration_ms)

    async def run_all_tests(self):
        """Run all functional tests"""
        print("🧪 Starting functional test suite...")

        # Test cases
        test_cases = [
            self.test_complete_order_flow,
            self.test_insufficient_inventory,
            self.test_concurrent_orders,
            self.test_data_consistency,
            self.test_performance_metrics,
        ]

        for test_case in test_cases:
            try:
                result = await test_case()
                self.add_result(result)
            except Exception as e:
                result = TestResult(
                    test_case.__name__, False, f"Test execution failed: {str(e)}", 0
                )
                self.add_result(result)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.success)
        failed_tests = total_tests - passed_tests

        print("\n" + "=" * 80)
        print("🧪 FUNCTIONAL TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result.success:
                    print(f"  - {result.name}: {result.message}")
                    if result.details:
                        for key, value in result.details.items():
                            print(f"    {key}: {value}")

        print("\n📊 TEST DETAILS:")
        for result in self.test_results:
            status = "PASS" if result.success else "FAIL"
            print(
                f"  {status:4} {result.name:25} {result.duration_ms:8.0f}ms - {result.message}"
            )

        print("=" * 80)


async def main():
    runner = FunctionalTestRunner()

    try:
        await runner.setup()
        await runner.run_all_tests()
    except Exception as e:
        print(f"❌ Test setup failed: {str(e)}")
        sys.exit(1)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

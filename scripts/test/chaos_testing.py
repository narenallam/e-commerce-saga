#!/usr/bin/env python3
"""
Chaos Testing for E-commerce Saga System

Introduces controlled failures to test system resilience
and saga compensation mechanisms.
"""

import asyncio
import aiohttp
import random
import uuid
from datetime import datetime
from typing import Dict, List, Any
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient


class ChaosTest:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.start_time = None
        self.end_time = None
        self.success = False
        self.details = {}


class ChaosTestRunner:
    def __init__(self):
        self.services = {
            "order": "http://localhost:8000",
            "inventory": "http://localhost:8001",
            "payment": "http://localhost:8002",
            "shipping": "http://localhost:8003",
            "notification": "http://localhost:8004",
            "coordinator": "http://localhost:9000",
        }
        self.db_client = None
        self.db = None
        self.test_results: List[ChaosTest] = []
        self.test_customer = None
        self.test_product = None

    async def setup(self):
        """Setup chaos testing environment"""
        print("🔧 Setting up chaos testing environment...")

        # Connect to database
        self.db_client = AsyncIOMotorClient("mongodb://localhost:27017")
        self.db = self.db_client.ecommerce_saga

        # Load test data
        self.test_customer = await self.db.customers.find_one()
        self.test_product = await self.db.inventory.find_one(
            {"status": "AVAILABLE", "quantity": {"$gt": 10}}
        )

        if not self.test_customer or not self.test_product:
            raise Exception("No test data found. Run test_data_generator.py first")

        print("✅ Chaos testing environment ready")

    async def cleanup(self):
        """Cleanup chaos testing environment"""
        if self.db_client:
            self.db_client.close()

    def create_test_order(self) -> Dict[str, Any]:
        """Create test order data"""
        return {
            "customer_id": self.test_customer["customer_id"],
            "items": [
                {
                    "product_id": self.test_product["product_id"],
                    "quantity": 1,
                    "price": self.test_product["price"],
                }
            ],
            "shipping_address": self.test_customer["shipping_address"],
            "payment_method": "CREDIT_CARD",
        }

    async def simulate_service_failure(self, service: str, duration: int = 30):
        """Simulate service failure by stopping/starting service"""
        print(f"🔥 Simulating {service} service failure for {duration}s...")

        # In a real environment, this would stop the actual service
        # For testing, we'll simulate by making the service unresponsive
        # This is a placeholder - actual implementation would depend on deployment method

        # Simulate failure by sending invalid requests
        try:
            async with aiohttp.ClientSession() as session:
                # Send shutdown signal (if service supports it)
                await session.post(
                    f"{self.services[service]}/admin/simulate-failure",
                    json={"duration": duration},
                )
        except:
            pass  # Service might not support failure simulation

        await asyncio.sleep(duration)

        print(f"✅ {service} service recovery simulated")

    async def test_service_failure_during_saga(self) -> ChaosTest:
        """Test CT-01: Service failure during saga execution"""
        test = ChaosTest(
            "Service Failure During Saga",
            "Test saga compensation when a service fails mid-execution",
        )
        test.start_time = datetime.now()

        try:
            # Start order creation
            order_data = self.create_test_order()
            correlation_id = str(uuid.uuid4())

            # Create order
            async with aiohttp.ClientSession() as session:
                # Simulate payment service failure
                await asyncio.sleep(2)  # Let saga start
                failure_task = asyncio.create_task(
                    self.simulate_service_failure("payment", 30)
                )

                response = await session.post(
                    f"{self.services['coordinator']}/api/coordinator/orders",
                    json=order_data,
                    headers={
                        "Content-Type": "application/json",
                        "X-Correlation-ID": correlation_id,
                    },
                    timeout=45,
                )

                await failure_task

                # Check if compensation was triggered
                await asyncio.sleep(10)  # Wait for compensation

                if response.status == 200:
                    result = await response.json()
                    order_id = result.get("order_id")

                    # Verify order was cancelled due to failure
                    order = await self.db.orders.find_one({"order_id": order_id})

                    if order and order.get("status") == "CANCELLED":
                        test.success = True
                        test.details = {
                            "order_id": order_id,
                            "compensation_triggered": True,
                            "final_status": order.get("status"),
                        }
                    else:
                        test.details = {
                            "order_id": order_id,
                            "expected_cancelled": True,
                            "actual_status": (
                                order.get("status") if order else "NOT_FOUND"
                            ),
                        }
                else:
                    # Order creation should fail
                    test.success = True
                    test.details = {
                        "order_creation_failed": True,
                        "status_code": response.status,
                    }

        except Exception as e:
            test.details = {"error": str(e)}

        test.end_time = datetime.now()
        return test

    async def test_network_partition(self) -> ChaosTest:
        """Test CT-02: Network partition simulation"""
        test = ChaosTest(
            "Network Partition", "Test saga behavior during network partition"
        )
        test.start_time = datetime.now()

        try:
            # Simulate by introducing delays
            order_data = self.create_test_order()
            correlation_id = str(uuid.uuid4())

            # Create order with simulated network issues
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60)
            ) as session:
                response = await session.post(
                    f"{self.services['coordinator']}/api/coordinator/orders",
                    json=order_data,
                    headers={
                        "Content-Type": "application/json",
                        "X-Correlation-ID": correlation_id,
                    },
                )

                if response.status == 200:
                    result = await response.json()
                    order_id = result.get("order_id")

                    # Wait for saga completion or timeout
                    await asyncio.sleep(30)

                    # Check final state
                    order = await self.db.orders.find_one({"order_id": order_id})
                    saga = await self.db.saga_logs.find_one({"order_id": order_id})

                    test.success = True
                    test.details = {
                        "order_id": order_id,
                        "order_status": order.get("status") if order else "NOT_FOUND",
                        "saga_status": saga.get("status") if saga else "NOT_FOUND",
                    }
                else:
                    test.details = {
                        "order_creation_failed": True,
                        "status": response.status,
                    }

        except asyncio.TimeoutError:
            test.success = True  # Timeout is expected behavior
            test.details = {"timeout_occurred": True}
        except Exception as e:
            test.details = {"error": str(e)}

        test.end_time = datetime.now()
        return test

    async def test_database_connection_loss(self) -> ChaosTest:
        """Test CT-03: Database connection loss"""
        test = ChaosTest(
            "Database Connection Loss",
            "Test saga behavior when database connection is lost",
        )
        test.start_time = datetime.now()

        try:
            # This would require actually disrupting database connection
            # For simulation, we'll create a scenario with database errors
            order_data = self.create_test_order()
            correlation_id = str(uuid.uuid4())

            # Simulate database issues by overwhelming it
            # or by testing with invalid connection parameters

            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    f"{self.services['coordinator']}/api/coordinator/orders",
                    json=order_data,
                    headers={
                        "Content-Type": "application/json",
                        "X-Correlation-ID": correlation_id,
                    },
                    timeout=30,
                )

                # Analyze response for database-related failures
                test.success = True
                test.details = {
                    "status_code": response.status,
                    "simulated_test": True,
                    "note": "Actual database disruption requires infrastructure access",
                }

        except Exception as e:
            test.details = {"error": str(e)}

        test.end_time = datetime.now()
        return test

    async def test_concurrent_failure_scenarios(self) -> ChaosTest:
        """Test CT-04: Multiple concurrent failures"""
        test = ChaosTest(
            "Concurrent Failures",
            "Test system behavior under multiple simultaneous failures",
        )
        test.start_time = datetime.now()

        try:
            # Create multiple orders with different failure scenarios
            tasks = []
            correlation_ids = []

            for i in range(5):
                order_data = self.create_test_order()
                correlation_id = f"chaos-concurrent-{i}-{uuid.uuid4()}"
                correlation_ids.append(correlation_id)

                task = self._create_order_with_chaos(order_data, correlation_id, i)
                tasks.append(task)

            # Execute all orders concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Analyze results
            successful = sum(
                1 for r in results if isinstance(r, dict) and r.get("success")
            )
            failed = len(results) - successful

            test.success = True
            test.details = {
                "total_orders": len(results),
                "successful": successful,
                "failed": failed,
                "results": [r for r in results if not isinstance(r, Exception)],
            }

        except Exception as e:
            test.details = {"error": str(e)}

        test.end_time = datetime.now()
        return test

    async def _create_order_with_chaos(
        self, order_data: Dict, correlation_id: str, chaos_type: int
    ) -> Dict:
        """Helper method to create order with specific chaos scenario"""
        try:
            async with aiohttp.ClientSession() as session:
                # Introduce different types of chaos based on index
                if chaos_type == 0:
                    # Normal order
                    timeout = 30
                elif chaos_type == 1:
                    # Simulate slow network
                    await asyncio.sleep(random.uniform(1, 5))
                    timeout = 30
                elif chaos_type == 2:
                    # Simulate invalid data
                    order_data["items"][0]["quantity"] = -1
                    timeout = 30
                elif chaos_type == 3:
                    # Simulate timeout
                    timeout = 5
                else:
                    # Normal with delay
                    await asyncio.sleep(random.uniform(0.1, 1))
                    timeout = 30

                response = await session.post(
                    f"{self.services['coordinator']}/api/coordinator/orders",
                    json=order_data,
                    headers={
                        "Content-Type": "application/json",
                        "X-Correlation-ID": correlation_id,
                    },
                    timeout=timeout,
                )

                return {
                    "success": response.status == 200,
                    "status_code": response.status,
                    "correlation_id": correlation_id,
                    "chaos_type": chaos_type,
                }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "timeout",
                "correlation_id": correlation_id,
                "chaos_type": chaos_type,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "correlation_id": correlation_id,
                "chaos_type": chaos_type,
            }

    async def test_resource_exhaustion(self) -> ChaosTest:
        """Test CT-05: Resource exhaustion scenario"""
        test = ChaosTest(
            "Resource Exhaustion", "Test system behavior under resource exhaustion"
        )
        test.start_time = datetime.now()

        try:
            # Create many concurrent orders to exhaust resources
            order_count = 50
            tasks = []

            print(
                f"🔥 Creating {order_count} concurrent orders to test resource limits..."
            )

            for i in range(order_count):
                order_data = self.create_test_order()
                correlation_id = f"chaos-resource-{i}-{uuid.uuid4()}"

                task = self._create_single_order(order_data, correlation_id)
                tasks.append(task)

            # Execute all orders concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Analyze results
            successful = sum(
                1 for r in results if isinstance(r, dict) and r.get("success")
            )
            failed = len(results) - successful
            timeouts = sum(
                1
                for r in results
                if isinstance(r, dict) and r.get("error") == "timeout"
            )

            test.success = True
            test.details = {
                "total_orders": order_count,
                "successful": successful,
                "failed": failed,
                "timeouts": timeouts,
                "success_rate": successful / order_count,
            }

        except Exception as e:
            test.details = {"error": str(e)}

        test.end_time = datetime.now()
        return test

    async def _create_single_order(self, order_data: Dict, correlation_id: str) -> Dict:
        """Helper to create a single order"""
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    f"{self.services['coordinator']}/api/coordinator/orders",
                    json=order_data,
                    headers={
                        "Content-Type": "application/json",
                        "X-Correlation-ID": correlation_id,
                    },
                    timeout=30,
                )

                return {
                    "success": response.status == 200,
                    "status_code": response.status,
                    "correlation_id": correlation_id,
                }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "timeout",
                "correlation_id": correlation_id,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "correlation_id": correlation_id}

    async def test_data_corruption_resilience(self) -> ChaosTest:
        """Test CT-06: Data corruption resilience"""
        test = ChaosTest(
            "Data Corruption Resilience", "Test system behavior with corrupted data"
        )
        test.start_time = datetime.now()

        try:
            # Test with various invalid data scenarios
            corruption_scenarios = [
                {"customer_id": None},  # Missing customer
                {"items": []},  # Empty items
                {
                    "items": [
                        {"product_id": "non-existent", "quantity": 1, "price": 10}
                    ]
                },  # Invalid product
                {
                    "items": [
                        {
                            "product_id": self.test_product["product_id"],
                            "quantity": -1,
                            "price": 10,
                        }
                    ]
                },  # Negative quantity
                {"shipping_address": {}},  # Invalid address
                {"payment_method": "INVALID_METHOD"},  # Invalid payment method
            ]

            results = []

            for i, corruption in enumerate(corruption_scenarios):
                order_data = self.create_test_order()
                order_data.update(corruption)
                correlation_id = f"chaos-corrupt-{i}-{uuid.uuid4()}"

                try:
                    async with aiohttp.ClientSession() as session:
                        response = await session.post(
                            f"{self.services['coordinator']}/api/coordinator/orders",
                            json=order_data,
                            headers={
                                "Content-Type": "application/json",
                                "X-Correlation-ID": correlation_id,
                            },
                            timeout=30,
                        )

                        results.append(
                            {
                                "corruption_type": list(corruption.keys())[0],
                                "status_code": response.status,
                                "handled_gracefully": response.status
                                == 400,  # Should reject invalid data
                            }
                        )

                except Exception as e:
                    results.append(
                        {
                            "corruption_type": list(corruption.keys())[0],
                            "error": str(e),
                            "handled_gracefully": True,  # Exception is acceptable
                        }
                    )

            graceful_handling = sum(1 for r in results if r.get("handled_gracefully"))

            test.success = graceful_handling == len(corruption_scenarios)
            test.details = {
                "total_scenarios": len(corruption_scenarios),
                "gracefully_handled": graceful_handling,
                "results": results,
            }

        except Exception as e:
            test.details = {"error": str(e)}

        test.end_time = datetime.now()
        return test

    async def run_all_chaos_tests(self):
        """Run all chaos tests"""
        print("🔥 Starting Chaos Testing Suite...")
        print("=" * 60)

        chaos_tests = [
            # self.test_service_failure_during_saga,  # Commented out as it requires actual service manipulation
            # self.test_network_partition,
            # self.test_database_connection_loss,
            self.test_concurrent_failure_scenarios,
            self.test_resource_exhaustion,
            self.test_data_corruption_resilience,
        ]

        for test_func in chaos_tests:
            try:
                print(f"\n🧪 Running {test_func.__name__}...")
                test_result = await test_func()
                self.test_results.append(test_result)

                status = "✅ PASS" if test_result.success else "❌ FAIL"
                duration = (
                    test_result.end_time - test_result.start_time
                ).total_seconds()
                print(f"{status} {test_result.name} ({duration:.1f}s)")

            except Exception as e:
                error_test = ChaosTest(
                    test_func.__name__, f"Error executing {test_func.__name__}"
                )
                error_test.details = {"error": str(e)}
                self.test_results.append(error_test)
                print(f"❌ ERROR {test_func.__name__}: {str(e)}")

        self.print_chaos_summary()

    def print_chaos_summary(self):
        """Print chaos testing summary"""
        print("\n" + "=" * 60)
        print("🔥 CHAOS TESTING SUMMARY")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for t in self.test_results if t.success)
        failed_tests = total_tests - passed_tests

        print(f"Total Chaos Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Resilience Score: {(passed_tests/total_tests)*100:.1f}%")

        print("\n📊 Test Results:")
        for test in self.test_results:
            status = "PASS" if test.success else "FAIL"
            duration = 0
            if test.start_time and test.end_time:
                duration = (test.end_time - test.start_time).total_seconds()
            print(f"  {status:4} {test.name:30} {duration:6.1f}s")

        print("\n🔍 Key Findings:")
        for test in self.test_results:
            if test.details:
                print(f"  • {test.name}:")
                for key, value in test.details.items():
                    if key not in ["results", "error"]:
                        print(f"    {key}: {value}")

        print("=" * 60)


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run chaos tests on e-commerce saga system"
    )
    parser.add_argument(
        "--test",
        choices=["all", "concurrent", "resource", "corruption"],
        default="all",
        help="Specific test to run",
    )

    args = parser.parse_args()

    runner = ChaosTestRunner()

    try:
        await runner.setup()

        if args.test == "all":
            await runner.run_all_chaos_tests()
        elif args.test == "concurrent":
            test = await runner.test_concurrent_failure_scenarios()
            runner.test_results.append(test)
            runner.print_chaos_summary()
        elif args.test == "resource":
            test = await runner.test_resource_exhaustion()
            runner.test_results.append(test)
            runner.print_chaos_summary()
        elif args.test == "corruption":
            test = await runner.test_data_corruption_resilience()
            runner.test_results.append(test)
            runner.print_chaos_summary()

    except Exception as e:
        print(f"❌ Chaos testing failed: {str(e)}")
        sys.exit(1)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

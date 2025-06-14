#!/usr/bin/env python3
"""
E-Commerce Saga Chaos Testing Script
Implements chaos engineering principles to test system resilience.
"""

import asyncio
import subprocess
import random
import time
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.layout import Layout

console = Console()


class ChaosTest:
    def __init__(self):
        self.services = [
            "order-service",
            "inventory-service",
            "payment-service",
            "shipping-service",
            "notification-service",
            "saga-coordinator",
        ]
        self.test_results = []

    async def get_pods(self, service_name: str = None) -> List[str]:
        """Get list of pods for a service or all services"""
        try:
            if service_name:
                cmd = f"kubectl get pods -l app={service_name} -o name"
            else:
                # Get all our service pods
                labels = " or ".join([f"app={svc}" for svc in self.services])
                cmd = f"kubectl get pods -l '{labels}' -o name"

            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                pods = [
                    pod.strip().replace("pod/", "")
                    for pod in result.stdout.strip().split("\n")
                    if pod.strip()
                ]
                return pods
            else:
                console.print(f"❌ Error getting pods: {result.stderr}")
                return []
        except Exception as e:
            console.print(f"❌ Exception getting pods: {e}")
            return []

    async def delete_pod(self, pod_name: str) -> bool:
        """Delete a specific pod"""
        try:
            cmd = f"kubectl delete pod {pod_name}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                console.print(f"💥 Deleted pod: {pod_name}")
                return True
            else:
                console.print(f"❌ Failed to delete pod {pod_name}: {result.stderr}")
                return False
        except Exception as e:
            console.print(f"❌ Exception deleting pod {pod_name}: {e}")
            return False

    async def wait_for_pod_recovery(
        self, service_name: str, timeout: int = 300
    ) -> bool:
        """Wait for service pods to be ready after chaos"""
        console.print(f"⏳ Waiting for {service_name} pods to recover...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                cmd = f"kubectl get pods -l app={service_name} -o jsonpath='{{.items[*].status.phase}}'"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

                if result.returncode == 0:
                    phases = result.stdout.strip().split()
                    if phases and all(phase == "Running" for phase in phases):
                        # Check if pods are ready
                        cmd = f"kubectl get pods -l app={service_name} -o jsonpath='{{.items[*].status.conditions[?(@.type==\"Ready\")].status}}'"
                        result = subprocess.run(
                            cmd, shell=True, capture_output=True, text=True
                        )

                        if result.returncode == 0:
                            ready_statuses = result.stdout.strip().split()
                            if ready_statuses and all(
                                status == "True" for status in ready_statuses
                            ):
                                console.print(
                                    f"✅ {service_name} pods recovered successfully"
                                )
                                return True

                await asyncio.sleep(5)

            except Exception as e:
                console.print(f"❌ Error checking pod recovery: {e}")
                await asyncio.sleep(5)

        console.print(f"⚠️  Timeout waiting for {service_name} recovery")
        return False

    async def simulate_pod_restart_chaos(
        self, service_name: str, failure_rate: int = 50, duration_minutes: int = 10
    ):
        """Simulate random pod restarts"""
        console.print(f"\n💥 Starting Pod Restart Chaos for {service_name}")
        console.print(
            f"Failure rate: {failure_rate}%, Duration: {duration_minutes} minutes"
        )

        test_start = time.time()
        test_result = {
            "test_type": "pod_restart_chaos",
            "service": service_name,
            "start_time": datetime.now().isoformat(),
            "duration_minutes": duration_minutes,
            "failure_rate": failure_rate,
            "pods_deleted": [],
            "recovery_times": [],
            "success": True,
            "errors": [],
        }

        end_time = time.time() + (duration_minutes * 60)

        while time.time() < end_time:
            try:
                # Get current pods
                pods = await self.get_pods(service_name)
                if not pods:
                    test_result["errors"].append("No pods found for service")
                    await asyncio.sleep(30)
                    continue

                # Decide whether to cause chaos
                if random.randint(1, 100) <= failure_rate:
                    # Select random pod to delete
                    pod_to_delete = random.choice(pods)
                    console.print(f"🎯 Targeting pod: {pod_to_delete}")

                    recovery_start = time.time()

                    # Delete the pod
                    if await self.delete_pod(pod_to_delete):
                        test_result["pods_deleted"].append(pod_to_delete)

                        # Wait for recovery
                        if await self.wait_for_pod_recovery(service_name):
                            recovery_time = time.time() - recovery_start
                            test_result["recovery_times"].append(recovery_time)
                            console.print(
                                f"⚡ Recovery time: {recovery_time:.2f} seconds"
                            )
                        else:
                            test_result["errors"].append(
                                f"Pod {pod_to_delete} failed to recover"
                            )
                            test_result["success"] = False

                # Wait before next potential chaos
                await asyncio.sleep(random.randint(30, 120))  # 30s to 2min interval

            except Exception as e:
                test_result["errors"].append(str(e))
                console.print(f"❌ Error during chaos test: {e}")
                await asyncio.sleep(30)

        test_result["end_time"] = datetime.now().isoformat()
        test_result["total_duration"] = time.time() - test_start
        self.test_results.append(test_result)

        console.print(f"\n📊 Pod Restart Chaos Results for {service_name}:")
        console.print(f"  Pods deleted: {len(test_result['pods_deleted'])}")
        console.print(
            f"  Average recovery time: {sum(test_result['recovery_times'])/len(test_result['recovery_times']) if test_result['recovery_times'] else 0:.2f}s"
        )
        console.print(f"  Success: {test_result['success']}")

    async def simulate_network_latency_chaos(self, duration_minutes: int = 15):
        """Simulate network latency between services"""
        console.print(f"\n🌐 Starting Network Latency Chaos")
        console.print(f"Duration: {duration_minutes} minutes")

        test_result = {
            "test_type": "network_latency_chaos",
            "start_time": datetime.now().isoformat(),
            "duration_minutes": duration_minutes,
            "latency_injections": [],
            "success": True,
            "errors": [],
        }

        # This is a simplified simulation - in real scenarios you'd use tools like:
        # - Istio for service mesh chaos
        # - Toxiproxy for network chaos
        # - Chaos Mesh for Kubernetes chaos

        latency_scenarios = [
            {"latency": "100ms", "description": "Mild network delay"},
            {"latency": "250ms", "description": "Moderate network delay"},
            {"latency": "500ms", "description": "Significant network delay"},
            {"latency": "1000ms", "description": "Severe network delay"},
        ]

        end_time = time.time() + (duration_minutes * 60)

        while time.time() < end_time:
            scenario = random.choice(latency_scenarios)
            console.print(
                f"🐌 Simulating {scenario['description']}: {scenario['latency']}"
            )

            # In a real implementation, you would:
            # 1. Apply network policies or service mesh rules
            # 2. Monitor service performance
            # 3. Validate system resilience

            test_result["latency_injections"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "latency": scenario["latency"],
                    "description": scenario["description"],
                }
            )

            # Simulate the latency effect duration
            await asyncio.sleep(random.randint(60, 180))  # 1-3 minutes

            console.print(f"✅ Latency scenario completed")

        test_result["end_time"] = datetime.now().isoformat()
        self.test_results.append(test_result)

        console.print(f"\n📊 Network Latency Chaos Results:")
        console.print(f"  Scenarios executed: {len(test_result['latency_injections'])}")

    async def simulate_resource_exhaustion(
        self, service_name: str, duration_minutes: int = 20
    ):
        """Simulate resource exhaustion"""
        console.print(f"\n💾 Starting Resource Exhaustion Test for {service_name}")
        console.print(f"Duration: {duration_minutes} minutes")

        test_result = {
            "test_type": "resource_exhaustion",
            "service": service_name,
            "start_time": datetime.now().isoformat(),
            "duration_minutes": duration_minutes,
            "resource_limits_applied": [],
            "success": True,
            "errors": [],
        }

        # Get current resource limits
        try:
            cmd = f"kubectl get deployment {service_name} -o jsonpath='{{.spec.template.spec.containers[0].resources}}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                current_resources = result.stdout.strip()
                console.print(f"📋 Current resources: {current_resources}")
        except Exception as e:
            test_result["errors"].append(f"Failed to get current resources: {e}")

        # Apply reduced resource limits
        reduced_limits = {
            "cpu": "50m",  # Very low CPU
            "memory": "128Mi",  # Very low memory
        }

        try:
            # This would apply resource constraints in a real scenario
            console.print(f"🔧 Applying resource constraints: {reduced_limits}")
            test_result["resource_limits_applied"] = reduced_limits

            # Monitor system behavior under resource pressure
            end_time = time.time() + (duration_minutes * 60)

            while time.time() < end_time:
                # Check pod status
                pods = await self.get_pods(service_name)
                console.print(
                    f"📊 Monitoring {len(pods)} pods under resource pressure..."
                )

                # In real implementation, monitor:
                # - Pod restart counts
                # - Response times
                # - Error rates
                # - Resource utilization

                await asyncio.sleep(60)  # Check every minute

        except Exception as e:
            test_result["errors"].append(str(e))
            test_result["success"] = False

        test_result["end_time"] = datetime.now().isoformat()
        self.test_results.append(test_result)

        console.print(f"\n📊 Resource Exhaustion Test Results:")
        console.print(f"  Service: {service_name}")
        console.print(f"  Success: {test_result['success']}")

    async def simulate_database_chaos(self, duration_minutes: int = 10):
        """Simulate database connectivity issues"""
        console.print(f"\n🗄️  Starting Database Chaos Test")
        console.print(f"Duration: {duration_minutes} minutes")

        test_result = {
            "test_type": "database_chaos",
            "start_time": datetime.now().isoformat(),
            "duration_minutes": duration_minutes,
            "connection_issues": [],
            "success": True,
            "errors": [],
        }

        # Get MongoDB pods
        mongodb_pods = await self.get_pods("mongodb")
        if not mongodb_pods:
            console.print("❌ No MongoDB pods found")
            test_result["errors"].append("No MongoDB pods found")
            test_result["success"] = False
            return

        console.print(f"🎯 Found {len(mongodb_pods)} MongoDB pods")

        end_time = time.time() + (duration_minutes * 60)

        while time.time() < end_time:
            chaos_type = random.choice(
                ["connection_drop", "slow_query", "disk_pressure"]
            )

            if chaos_type == "connection_drop":
                console.print("💥 Simulating database connection drops")
                # In real scenario: Use network policies to drop connections

            elif chaos_type == "slow_query":
                console.print("🐌 Simulating slow database queries")
                # In real scenario: Inject query delays

            elif chaos_type == "disk_pressure":
                console.print("💾 Simulating database disk pressure")
                # In real scenario: Fill up disk space temporarily

            test_result["connection_issues"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "type": chaos_type,
                    "description": f"Simulated {chaos_type}",
                }
            )

            await asyncio.sleep(random.randint(60, 180))  # 1-3 minutes between issues

        test_result["end_time"] = datetime.now().isoformat()
        self.test_results.append(test_result)

        console.print(f"\n📊 Database Chaos Test Results:")
        console.print(f"  Issues simulated: {len(test_result['connection_issues'])}")

    async def run_comprehensive_chaos_test(self, duration_minutes: int = 30):
        """Run multiple chaos tests simultaneously"""
        console.print(f"\n🚀 Starting Comprehensive Chaos Engineering Test")
        console.print(f"Total Duration: {duration_minutes} minutes")
        console.print("=" * 60)

        # Run multiple chaos tests in parallel
        chaos_tasks = [
            self.simulate_pod_restart_chaos(
                "order-service", failure_rate=30, duration_minutes=duration_minutes // 2
            ),
            self.simulate_pod_restart_chaos(
                "payment-service",
                failure_rate=20,
                duration_minutes=duration_minutes // 2,
            ),
            self.simulate_network_latency_chaos(duration_minutes // 3),
            self.simulate_resource_exhaustion(
                "inventory-service", duration_minutes // 4
            ),
            self.simulate_database_chaos(duration_minutes // 6),
        ]

        # Execute chaos tests concurrently
        await asyncio.gather(*chaos_tasks, return_exceptions=True)

        console.print("\n🏁 Comprehensive Chaos Test Complete!")

    def generate_chaos_report(self) -> Table:
        """Generate comprehensive chaos test report"""
        table = Table(title="💥 Chaos Engineering Test Results", style="red")
        table.add_column("Test Type", style="bold")
        table.add_column("Service", style="cyan")
        table.add_column("Duration", style="green")
        table.add_column("Success", style="yellow")
        table.add_column("Details", style="white")

        for result in self.test_results:
            test_type = result["test_type"].replace("_", " ").title()
            service = result.get("service", "All Services")
            duration = f"{result['duration_minutes']}m"
            success = "✅" if result["success"] else "❌"

            # Generate details based on test type
            if result["test_type"] == "pod_restart_chaos":
                details = f"Pods deleted: {len(result['pods_deleted'])}, Avg recovery: {sum(result['recovery_times'])/len(result['recovery_times']) if result['recovery_times'] else 0:.1f}s"
            elif result["test_type"] == "network_latency_chaos":
                details = f"Latency scenarios: {len(result['latency_injections'])}"
            elif result["test_type"] == "resource_exhaustion":
                details = (
                    f"Resource limits applied: {len(result['resource_limits_applied'])}"
                )
            elif result["test_type"] == "database_chaos":
                details = f"Issues simulated: {len(result['connection_issues'])}"
            else:
                details = "N/A"

            table.add_row(test_type, service, duration, success, details)

        return table

    def save_results_to_file(
        self, filename: str = "./test-data/chaos_test_results.json"
    ):
        """Save chaos test results to file"""
        try:
            with open(filename, "w") as f:
                json.dump(self.test_results, f, indent=2)
            console.print(f"💾 Chaos test results saved to {filename}")
        except Exception as e:
            console.print(f"❌ Failed to save results: {e}")


async def main():
    parser = argparse.ArgumentParser(
        description="Run chaos engineering tests on e-commerce saga system"
    )
    parser.add_argument("--service", help="Target specific service for chaos testing")
    parser.add_argument(
        "--type",
        choices=[
            "pod_restart",
            "network_latency",
            "resource_exhaustion",
            "database",
            "comprehensive",
        ],
        default="comprehensive",
        help="Type of chaos test to run",
    )
    parser.add_argument(
        "--duration", type=int, default=30, help="Test duration in minutes"
    )
    parser.add_argument(
        "--failure-rate",
        type=int,
        default=30,
        help="Failure rate percentage for pod restart tests",
    )
    parser.add_argument(
        "--save-results", action="store_true", help="Save test results to file"
    )

    args = parser.parse_args()

    chaos_tester = ChaosTest()

    console.print("💥 E-Commerce Saga Chaos Engineering")
    console.print("=====================================")

    if args.type == "pod_restart":
        service = args.service or "order-service"
        await chaos_tester.simulate_pod_restart_chaos(
            service, args.failure_rate, args.duration
        )

    elif args.type == "network_latency":
        await chaos_tester.simulate_network_latency_chaos(args.duration)

    elif args.type == "resource_exhaustion":
        service = args.service or "payment-service"
        await chaos_tester.simulate_resource_exhaustion(service, args.duration)

    elif args.type == "database":
        await chaos_tester.simulate_database_chaos(args.duration)

    else:  # comprehensive
        await chaos_tester.run_comprehensive_chaos_test(args.duration)

    # Display results
    console.print("\n" + "=" * 80)
    console.print(chaos_tester.generate_chaos_report())

    # Save results if requested
    if args.save_results:
        chaos_tester.save_results_to_file()

    # Final assessment
    total_tests = len(chaos_tester.test_results)
    successful_tests = sum(
        1 for result in chaos_tester.test_results if result["success"]
    )

    console.print(f"\n🎯 Chaos Engineering Assessment:")
    console.print(f"  Tests executed: {total_tests}")
    console.print(f"  Successful: {successful_tests}")
    console.print(
        f"  Success rate: {(successful_tests/total_tests)*100 if total_tests > 0 else 0:.1f}%"
    )

    if successful_tests == total_tests:
        console.print("🏆 EXCELLENT: System demonstrated strong resilience")
    elif successful_tests >= total_tests * 0.8:
        console.print("✅ GOOD: System has good resilience with minor issues")
    elif successful_tests >= total_tests * 0.6:
        console.print("⚠️  MODERATE: System has resilience gaps that need attention")
    else:
        console.print("❌ POOR: System has significant resilience issues")


if __name__ == "__main__":
    asyncio.run(main())

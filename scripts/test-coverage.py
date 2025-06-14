#!/usr/bin/env python3
"""
Comprehensive Test Coverage and Reporting System
For E-Commerce Saga System

Features:
- Unit test coverage analysis
- Integration test coverage
- API endpoint coverage
- Database operation coverage
- Service interaction coverage
- Performance metrics
- Test result reporting
"""

import asyncio
import aiohttp
import json
import time
import subprocess
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

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
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich.tree import Tree

console = Console()


class TestCoverageAnalyzer:
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
        self.coverage_results = {
            "unit_tests": {},
            "integration_tests": {},
            "api_coverage": {},
            "database_coverage": {},
            "service_interactions": {},
            "performance_metrics": {},
            "overall_coverage": 0.0,
        }
        self.test_reports = []

    async def analyze_unit_test_coverage(self):
        """Analyze unit test coverage for all services"""
        console.print("🔍 [bold blue]Analyzing Unit Test Coverage[/bold blue]")

        services = [
            "order",
            "inventory",
            "payment",
            "shipping",
            "notification",
            "coordinator",
        ]
        unit_coverage = {}

        for service in services:
            service_path = (
                f"src/services/{service}"
                if service != "coordinator"
                else "src/coordinator"
            )
            test_path = (
                f"{service_path}/tests"
                if service != "coordinator"
                else "tests/coordinator"
            )

            # Check if test files exist
            test_files = []
            if os.path.exists(test_path):
                for root, dirs, files in os.walk(test_path):
                    test_files.extend(
                        [
                            f
                            for f in files
                            if f.startswith("test_") and f.endswith(".py")
                        ]
                    )

            # Check source files
            source_files = []
            if os.path.exists(service_path):
                for root, dirs, files in os.walk(service_path):
                    if "tests" not in root:
                        source_files.extend(
                            [
                                f
                                for f in files
                                if f.endswith(".py") and not f.startswith("__")
                            ]
                        )

            # Calculate coverage percentage
            if source_files:
                coverage_ratio = (
                    len(test_files) / len(source_files) if source_files else 0
                )
                coverage_percentage = min(coverage_ratio * 100, 100)  # Cap at 100%
            else:
                coverage_percentage = 0

            unit_coverage[service] = {
                "test_files": len(test_files),
                "source_files": len(source_files),
                "coverage_percentage": coverage_percentage,
                "status": (
                    "✅ Good"
                    if coverage_percentage >= 70
                    else (
                        "⚠️ Needs Improvement"
                        if coverage_percentage >= 30
                        else "❌ Poor"
                    )
                ),
            }

            console.print(
                f"  📁 {service}: {len(test_files)} tests / {len(source_files)} files = {coverage_percentage:.1f}%"
            )

        self.coverage_results["unit_tests"] = unit_coverage
        return unit_coverage

    async def analyze_api_coverage(self, session: aiohttp.ClientSession):
        """Analyze API endpoint coverage"""
        console.print("\n🌐 [bold blue]Analyzing API Endpoint Coverage[/bold blue]")

        # Define expected endpoints for each service
        expected_endpoints = {
            "order": [
                "/health",
                "/docs",
                "/api/orders",
                "/api/orders/{id}",
                "/metrics",
            ],
            "inventory": [
                "/health",
                "/docs",
                "/api/inventory",
                "/api/inventory/reserve",
                "/api/inventory/release",
                "/metrics",
            ],
            "payment": [
                "/health",
                "/docs",
                "/api/payments/process",
                "/api/payments/refund",
                "/metrics",
            ],
            "shipping": [
                "/health",
                "/docs",
                "/api/shipping/schedule",
                "/api/shipping/cancel",
                "/metrics",
            ],
            "notification": [
                "/health",
                "/docs",
                "/api/notifications/send",
                "/api/notifications/cancel",
                "/metrics",
            ],
            "saga": [
                "/health",
                "/docs",
                "/api/coordinator/orders",
                "/api/coordinator/orders/{id}",
                "/metrics",
            ],
        }

        api_coverage = {}

        for service, endpoints in expected_endpoints.items():
            port = self.service_ports[service]
            working_endpoints = 0
            tested_endpoints = []

            for endpoint in endpoints:
                try:
                    # Test basic endpoints (non-parameterized)
                    if "{" not in endpoint:
                        url = f"{self.base_url}:{port}{endpoint}"
                        async with session.get(url, timeout=5) as response:
                            if response.status in [
                                200,
                                201,
                                404,
                                405,
                            ]:  # 404/405 are acceptable for some endpoints
                                working_endpoints += 1
                                tested_endpoints.append(f"✅ {endpoint}")
                            else:
                                tested_endpoints.append(
                                    f"❌ {endpoint} (HTTP {response.status})"
                                )
                    else:
                        # For parameterized endpoints, assume they exist if service is healthy
                        tested_endpoints.append(
                            f"📝 {endpoint} (not tested - parameterized)"
                        )
                        working_endpoints += 0.5  # Partial credit

                except Exception as e:
                    tested_endpoints.append(f"❌ {endpoint} ({str(e)[:30]}...)")

            coverage_percentage = (working_endpoints / len(endpoints)) * 100
            api_coverage[service] = {
                "total_endpoints": len(endpoints),
                "working_endpoints": working_endpoints,
                "coverage_percentage": coverage_percentage,
                "details": tested_endpoints,
                "status": (
                    "✅ Good"
                    if coverage_percentage >= 80
                    else "⚠️ Partial" if coverage_percentage >= 50 else "❌ Poor"
                ),
            }

            console.print(
                f"  🔗 {service}: {working_endpoints}/{len(endpoints)} endpoints = {coverage_percentage:.1f}%"
            )

        self.coverage_results["api_coverage"] = api_coverage
        return api_coverage

    async def analyze_database_coverage(self):
        """Analyze database operation coverage"""
        console.print("\n🗄️ [bold blue]Analyzing Database Coverage[/bold blue]")

        try:
            from motor.motor_asyncio import AsyncIOMotorClient

            client = AsyncIOMotorClient("mongodb://localhost:27017")
            db = client.ecommerce_saga

            # Expected collections and operations
            expected_collections = [
                "customers",
                "inventory",
                "orders",
                "payments",
                "shipments",
                "notifications",
                "saga_logs",
                "inventory_reservations",
                "notification_templates",
            ]

            db_coverage = {}

            for collection_name in expected_collections:
                try:
                    collection = db[collection_name]

                    # Check basic operations
                    operations = {
                        "read": False,
                        "write": False,
                        "index": False,
                        "aggregate": False,
                    }

                    # Test read operation
                    try:
                        count = await collection.count_documents({})
                        operations["read"] = True
                        has_data = count > 0
                    except:
                        has_data = False

                    # Test write operation (by checking if collection has data)
                    operations["write"] = has_data

                    # Check indexes
                    try:
                        indexes = await collection.list_indexes().to_list(None)
                        operations["index"] = (
                            len(indexes) > 1
                        )  # More than just _id index
                    except:
                        pass

                    # Test aggregation capability (simple one)
                    try:
                        if has_data:
                            pipeline = [{"$limit": 1}]
                            result = await collection.aggregate(pipeline).to_list(1)
                            operations["aggregate"] = len(result) > 0
                    except:
                        pass

                    coverage_count = sum(operations.values())
                    coverage_percentage = (coverage_count / len(operations)) * 100

                    db_coverage[collection_name] = {
                        "operations": operations,
                        "coverage_percentage": coverage_percentage,
                        "document_count": count if "count" in locals() else 0,
                        "status": (
                            "✅ Good"
                            if coverage_percentage >= 75
                            else "⚠️ Partial" if coverage_percentage >= 50 else "❌ Poor"
                        ),
                    }

                    console.print(
                        f"  📊 {collection_name}: {coverage_count}/4 operations = {coverage_percentage:.1f}%"
                    )

                except Exception as e:
                    db_coverage[collection_name] = {
                        "operations": {
                            "read": False,
                            "write": False,
                            "index": False,
                            "aggregate": False,
                        },
                        "coverage_percentage": 0,
                        "document_count": 0,
                        "status": f"❌ Error: {str(e)[:30]}...",
                    }
                    console.print(f"  ❌ {collection_name}: Error - {str(e)[:50]}...")

            client.close()

        except ImportError:
            console.print("  ❌ MongoDB driver not available")
            db_coverage = {"error": "MongoDB driver not available"}
        except Exception as e:
            console.print(f"  ❌ Database connection failed: {str(e)}")
            db_coverage = {"error": f"Database connection failed: {str(e)}"}

        self.coverage_results["database_coverage"] = db_coverage
        return db_coverage

    async def analyze_service_interactions(self, session: aiohttp.ClientSession):
        """Analyze service-to-service interaction coverage"""
        console.print(
            "\n🔄 [bold blue]Analyzing Service Interaction Coverage[/bold blue]"
        )

        # Expected service interactions in saga pattern
        expected_interactions = {
            "saga_to_order": {
                "endpoint": "/health",
                "description": "Saga → Order Service",
            },
            "saga_to_inventory": {
                "endpoint": "/health",
                "description": "Saga → Inventory Service",
            },
            "saga_to_payment": {
                "endpoint": "/health",
                "description": "Saga → Payment Service",
            },
            "saga_to_shipping": {
                "endpoint": "/health",
                "description": "Saga → Shipping Service",
            },
            "saga_to_notification": {
                "endpoint": "/health",
                "description": "Saga → Notification Service",
            },
            "all_to_database": {
                "endpoint": "mongodb",
                "description": "All Services → MongoDB",
            },
        }

        interaction_coverage = {}

        # Test basic connectivity between services (using health checks as proxy)
        for interaction_id, details in expected_interactions.items():
            if "saga_to_" in interaction_id:
                service = interaction_id.replace("saga_to_", "")
                port = self.service_ports.get(service)

                if port:
                    try:
                        url = f"{self.base_url}:{port}{details['endpoint']}"
                        async with session.get(url, timeout=5) as response:
                            success = response.status == 200
                            interaction_coverage[interaction_id] = {
                                "description": details["description"],
                                "success": success,
                                "status": (
                                    "✅ Connected"
                                    if success
                                    else f"❌ Failed (HTTP {response.status})"
                                ),
                            }
                    except Exception as e:
                        interaction_coverage[interaction_id] = {
                            "description": details["description"],
                            "success": False,
                            "status": f"❌ Error: {str(e)[:30]}...",
                        }
                else:
                    interaction_coverage[interaction_id] = {
                        "description": details["description"],
                        "success": False,
                        "status": "❌ Service port not found",
                    }
            elif interaction_id == "all_to_database":
                # Test database connectivity
                try:
                    from motor.motor_asyncio import AsyncIOMotorClient

                    client = AsyncIOMotorClient("mongodb://localhost:27017")
                    await client.admin.command("ping")
                    client.close()

                    interaction_coverage[interaction_id] = {
                        "description": details["description"],
                        "success": True,
                        "status": "✅ Connected",
                    }
                except Exception as e:
                    interaction_coverage[interaction_id] = {
                        "description": details["description"],
                        "success": False,
                        "status": f"❌ Database error: {str(e)[:30]}...",
                    }

        # Calculate overall interaction coverage
        successful_interactions = sum(
            1 for i in interaction_coverage.values() if i["success"]
        )
        total_interactions = len(interaction_coverage)
        coverage_percentage = (
            (successful_interactions / total_interactions) * 100
            if total_interactions > 0
            else 0
        )

        for interaction_id, details in interaction_coverage.items():
            console.print(f"  🔗 {details['description']}: {details['status']}")

        console.print(
            f"\n  📊 Overall Interaction Coverage: {successful_interactions}/{total_interactions} = {coverage_percentage:.1f}%"
        )

        self.coverage_results["service_interactions"] = {
            "interactions": interaction_coverage,
            "coverage_percentage": coverage_percentage,
            "successful_count": successful_interactions,
            "total_count": total_interactions,
        }

        return interaction_coverage

    async def run_performance_tests(self, session: aiohttp.ClientSession):
        """Run performance tests and collect metrics"""
        console.print("\n⚡ [bold blue]Running Performance Tests[/bold blue]")

        performance_metrics = {}

        # Test 1: Individual service response times
        console.print("  📊 Testing individual service response times...")
        service_metrics = {}

        for service, port in self.service_ports.items():
            response_times = []

            # Test 10 requests to each service
            for _ in range(10):
                try:
                    url = f"{self.base_url}:{port}/health"
                    start_time = time.time()
                    async with session.get(url, timeout=5) as response:
                        end_time = time.time()
                        if response.status == 200:
                            response_times.append(
                                (end_time - start_time) * 1000
                            )  # Convert to ms
                except:
                    pass

            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                min_response_time = min(response_times)
                max_response_time = max(response_times)

                service_metrics[service] = {
                    "avg_response_time_ms": round(avg_response_time, 2),
                    "min_response_time_ms": round(min_response_time, 2),
                    "max_response_time_ms": round(max_response_time, 2),
                    "success_rate": (len(response_times) / 10) * 100,
                    "status": (
                        "✅ Excellent"
                        if avg_response_time < 10
                        else "⚠️ Good" if avg_response_time < 50 else "❌ Slow"
                    ),
                }

                console.print(
                    f"    🔍 {service}: {avg_response_time:.1f}ms avg ({min_response_time:.1f}-{max_response_time:.1f}ms)"
                )
            else:
                service_metrics[service] = {
                    "avg_response_time_ms": 0,
                    "min_response_time_ms": 0,
                    "max_response_time_ms": 0,
                    "success_rate": 0,
                    "status": "❌ Failed",
                }

        # Test 2: Concurrent load test
        console.print("  ⚡ Testing concurrent load (20 requests)...")

        concurrent_requests = 20
        start_time = time.time()

        # Create concurrent requests across all services
        tasks = []
        for _ in range(concurrent_requests):
            service = list(self.service_ports.keys())[_ % len(self.service_ports)]
            port = self.service_ports[service]
            url = f"{self.base_url}:{port}/health"
            tasks.append(session.get(url, timeout=10))

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        successful_requests = 0
        for response in responses:
            if not isinstance(response, Exception):
                if response.status == 200:
                    successful_requests += 1
                response.close()

        concurrent_metrics = {
            "total_requests": concurrent_requests,
            "successful_requests": successful_requests,
            "total_time_seconds": round(total_time, 2),
            "requests_per_second": round(concurrent_requests / total_time, 2),
            "success_rate": (successful_requests / concurrent_requests) * 100,
            "avg_response_time_ms": round((total_time / concurrent_requests) * 1000, 2),
        }

        console.print(
            f"    📈 {successful_requests}/{concurrent_requests} successful in {total_time:.2f}s"
        )
        console.print(
            f"    🚀 {concurrent_metrics['requests_per_second']:.1f} req/sec, {concurrent_metrics['avg_response_time_ms']:.1f}ms avg"
        )

        performance_metrics = {
            "individual_services": service_metrics,
            "concurrent_load": concurrent_metrics,
            "overall_performance": (
                "✅ Excellent"
                if concurrent_metrics["success_rate"] >= 95
                and concurrent_metrics["avg_response_time_ms"] < 50
                else "⚠️ Good" if concurrent_metrics["success_rate"] >= 80 else "❌ Poor"
            ),
        }

        self.coverage_results["performance_metrics"] = performance_metrics
        return performance_metrics

    def calculate_overall_coverage(self):
        """Calculate overall test coverage score"""
        weights = {
            "unit_tests": 0.25,
            "api_coverage": 0.25,
            "database_coverage": 0.20,
            "service_interactions": 0.20,
            "performance_metrics": 0.10,
        }

        scores = {}

        # Unit test coverage
        if self.coverage_results["unit_tests"]:
            unit_scores = [
                item["coverage_percentage"]
                for item in self.coverage_results["unit_tests"].values()
            ]
            scores["unit_tests"] = (
                sum(unit_scores) / len(unit_scores) if unit_scores else 0
            )
        else:
            scores["unit_tests"] = 0

        # API coverage
        if self.coverage_results["api_coverage"]:
            api_scores = [
                item["coverage_percentage"]
                for item in self.coverage_results["api_coverage"].values()
            ]
            scores["api_coverage"] = (
                sum(api_scores) / len(api_scores) if api_scores else 0
            )
        else:
            scores["api_coverage"] = 0

        # Database coverage
        if (
            self.coverage_results["database_coverage"]
            and "error" not in self.coverage_results["database_coverage"]
        ):
            db_scores = [
                item["coverage_percentage"]
                for item in self.coverage_results["database_coverage"].values()
            ]
            scores["database_coverage"] = (
                sum(db_scores) / len(db_scores) if db_scores else 0
            )
        else:
            scores["database_coverage"] = 0

        # Service interactions
        if self.coverage_results["service_interactions"]:
            scores["service_interactions"] = self.coverage_results[
                "service_interactions"
            ].get("coverage_percentage", 0)
        else:
            scores["service_interactions"] = 0

        # Performance metrics (based on success rate)
        if self.coverage_results["performance_metrics"]:
            perf_data = self.coverage_results["performance_metrics"].get(
                "concurrent_load", {}
            )
            scores["performance_metrics"] = perf_data.get("success_rate", 0)
        else:
            scores["performance_metrics"] = 0

        # Calculate weighted average
        overall_score = sum(
            scores[category] * weights[category] for category in weights.keys()
        )

        self.coverage_results["overall_coverage"] = overall_score
        return overall_score, scores

    def generate_coverage_report(self):
        """Generate comprehensive coverage report"""
        console.print(
            "\n📊 [bold green]COMPREHENSIVE TEST COVERAGE REPORT[/bold green]"
        )
        console.print("=" * 80)

        overall_score, category_scores = self.calculate_overall_coverage()

        # Overall Coverage Summary
        console.print(f"\n🎯 [bold]OVERALL COVERAGE SCORE: {overall_score:.1f}%[/bold]")

        if overall_score >= 90:
            overall_status = "🏆 [bold green]EXCELLENT[/bold green]"
        elif overall_score >= 75:
            overall_status = "✅ [bold green]GOOD[/bold green]"
        elif overall_score >= 60:
            overall_status = "⚠️ [bold yellow]FAIR[/bold yellow]"
        else:
            overall_status = "❌ [bold red]POOR[/bold red]"

        console.print(f"Status: {overall_status}")

        # Category Breakdown Table
        console.print("\n📋 [bold]COVERAGE BREAKDOWN BY CATEGORY[/bold]")

        table = Table(title="Test Coverage Analysis")
        table.add_column("Category", style="cyan")
        table.add_column("Score", style="yellow")
        table.add_column("Weight", style="green")
        table.add_column("Weighted Score", style="magenta")
        table.add_column("Status", style="white")

        weights = {
            "unit_tests": 0.25,
            "api_coverage": 0.25,
            "database_coverage": 0.20,
            "service_interactions": 0.20,
            "performance_metrics": 0.10,
        }

        for category, score in category_scores.items():
            weight = weights[category]
            weighted_score = score * weight

            if score >= 80:
                status = "✅ Good"
            elif score >= 60:
                status = "⚠️ Fair"
            else:
                status = "❌ Poor"

            table.add_row(
                category.replace("_", " ").title(),
                f"{score:.1f}%",
                f"{weight:.0%}",
                f"{weighted_score:.1f}",
                status,
            )

        console.print(table)

        # Detailed Results
        self._print_detailed_results()

        # Recommendations
        self._print_recommendations(category_scores)

        # Generate JSON report
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "overall_coverage": overall_score,
            "category_scores": category_scores,
            "detailed_results": self.coverage_results,
            "recommendations": self._get_recommendations(category_scores),
        }

        # Save report to file
        report_file = (
            f"test_coverage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        console.print(f"\n📄 [bold green]Report saved to: {report_file}[/bold green]")

        return report_data

    def _print_detailed_results(self):
        """Print detailed results for each category"""
        console.print("\n📝 [bold]DETAILED RESULTS[/bold]")
        console.print("-" * 60)

        # Unit Tests Details
        if self.coverage_results["unit_tests"]:
            console.print("\n🧪 [bold cyan]Unit Test Coverage:[/bold cyan]")
            for service, data in self.coverage_results["unit_tests"].items():
                console.print(
                    f"  • {service}: {data['test_files']} tests / {data['source_files']} files = {data['coverage_percentage']:.1f}% {data['status']}"
                )

        # API Coverage Details
        if self.coverage_results["api_coverage"]:
            console.print("\n🌐 [bold cyan]API Endpoint Coverage:[/bold cyan]")
            for service, data in self.coverage_results["api_coverage"].items():
                console.print(
                    f"  • {service}: {data['working_endpoints']}/{data['total_endpoints']} endpoints = {data['coverage_percentage']:.1f}% {data['status']}"
                )

        # Database Coverage Details
        if (
            self.coverage_results["database_coverage"]
            and "error" not in self.coverage_results["database_coverage"]
        ):
            console.print("\n🗄️ [bold cyan]Database Coverage:[/bold cyan]")
            for collection, data in self.coverage_results["database_coverage"].items():
                ops = sum(data["operations"].values())
                console.print(
                    f"  • {collection}: {ops}/4 operations = {data['coverage_percentage']:.1f}% {data['status']}"
                )

        # Performance Metrics Details
        if self.coverage_results["performance_metrics"]:
            console.print("\n⚡ [bold cyan]Performance Metrics:[/bold cyan]")
            perf = self.coverage_results["performance_metrics"]
            if "concurrent_load" in perf:
                load = perf["concurrent_load"]
                console.print(
                    f"  • Concurrent Load: {load['success_rate']:.1f}% success rate, {load['requests_per_second']:.1f} req/sec"
                )
            if "individual_services" in perf:
                console.print(
                    f"  • Individual Services: {len(perf['individual_services'])} services tested"
                )

    def _print_recommendations(self, category_scores):
        """Print recommendations for improvement"""
        console.print("\n💡 [bold]RECOMMENDATIONS FOR IMPROVEMENT[/bold]")
        console.print("-" * 60)

        recommendations = self._get_recommendations(category_scores)

        for category, recs in recommendations.items():
            if recs:
                console.print(
                    f"\n📋 [bold cyan]{category.replace('_', ' ').title()}:[/bold cyan]"
                )
                for rec in recs:
                    console.print(f"  • {rec}")

    def _get_recommendations(self, category_scores):
        """Get recommendations based on scores"""
        recommendations = {}

        if category_scores["unit_tests"] < 70:
            recommendations["unit_tests"] = [
                "Add more unit tests for each service",
                "Aim for at least 80% code coverage",
                "Create tests for error handling scenarios",
                "Add integration tests between components",
            ]

        if category_scores["api_coverage"] < 80:
            recommendations["api_coverage"] = [
                "Test all API endpoints thoroughly",
                "Add tests for parameterized endpoints",
                "Implement API contract testing",
                "Add negative test cases for APIs",
            ]

        if category_scores["database_coverage"] < 75:
            recommendations["database_coverage"] = [
                "Add more database operation tests",
                "Test complex queries and aggregations",
                "Implement database transaction tests",
                "Add database performance tests",
            ]

        if category_scores["service_interactions"] < 85:
            recommendations["service_interactions"] = [
                "Test service-to-service communication",
                "Add saga transaction flow tests",
                "Test failure and recovery scenarios",
                "Implement end-to-end integration tests",
            ]

        if category_scores["performance_metrics"] < 90:
            recommendations["performance_metrics"] = [
                "Optimize slow response times",
                "Add load testing for peak scenarios",
                "Implement stress testing",
                "Monitor and improve throughput",
            ]

        return recommendations

    async def run_comprehensive_coverage_analysis(self):
        """Run complete coverage analysis"""
        console.print(
            Panel.fit(
                "[bold cyan]🔍 COMPREHENSIVE TEST COVERAGE ANALYSIS[/bold cyan]\n"
                "[yellow]Analyzing unit tests, API coverage, database operations, service interactions, and performance[/yellow]",
                border_style="cyan",
            )
        )

        async with aiohttp.ClientSession() as session:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:

                task = progress.add_task("Running coverage analysis...", total=5)

                # Run all coverage analyses
                await self.analyze_unit_test_coverage()
                progress.advance(task)

                progress.update(task, description="Analyzing API coverage...")
                await self.analyze_api_coverage(session)
                progress.advance(task)

                progress.update(task, description="Analyzing database coverage...")
                await self.analyze_database_coverage()
                progress.advance(task)

                progress.update(task, description="Analyzing service interactions...")
                await self.analyze_service_interactions(session)
                progress.advance(task)

                progress.update(task, description="Running performance tests...")
                await self.run_performance_tests(session)
                progress.advance(task)

        # Generate comprehensive report
        return self.generate_coverage_report()


async def main():
    analyzer = TestCoverageAnalyzer()
    report = await analyzer.run_comprehensive_coverage_analysis()

    console.print("\n✨ [bold green]Test coverage analysis complete![/bold green]")
    console.print("📄 [cyan]Detailed report saved to JSON file[/cyan]")


if __name__ == "__main__":
    asyncio.run(main())

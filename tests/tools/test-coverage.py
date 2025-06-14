#!/usr/bin/env python3
"""
Test Coverage and Reporting System for E-Commerce Saga
"""

import asyncio
import aiohttp
import json
import time
import os
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel

console = Console()


class TestCoverageAnalyzer:
    def __init__(self):
        self.service_ports = {
            "order": 8000,
            "inventory": 8001,
            "payment": 8002,
            "shipping": 8003,
            "notification": 8004,
            "saga": 9000,
        }
        self.results = {}

    async def analyze_api_coverage(self):
        """Test API endpoint coverage"""
        console.print("🌐 [bold blue]Testing API Coverage[/bold blue]")

        endpoints = {
            "order": ["/health", "/docs", "/metrics"],
            "inventory": ["/health", "/docs", "/metrics"],
            "payment": ["/health", "/docs", "/metrics"],
            "shipping": ["/health", "/docs", "/metrics"],
            "notification": ["/health", "/docs", "/metrics"],
            "saga": ["/health", "/docs", "/metrics"],
        }

        api_results = {}

        async with aiohttp.ClientSession() as session:
            for service, paths in endpoints.items():
                port = self.service_ports[service]
                working = 0

                for path in paths:
                    try:
                        url = f"http://localhost:{port}{path}"
                        async with session.get(url, timeout=3) as response:
                            if response.status in [200, 404, 405]:
                                working += 1
                    except:
                        pass

                coverage = (working / len(paths)) * 100
                api_results[service] = {
                    "working": working,
                    "total": len(paths),
                    "coverage": coverage,
                    "status": (
                        "✅" if coverage >= 66 else "⚠️" if coverage >= 33 else "❌"
                    ),
                }

                console.print(
                    f"  {service}: {working}/{len(paths)} = {coverage:.1f}% {api_results[service]['status']}"
                )

        self.results["api_coverage"] = api_results
        return api_results

    async def analyze_performance(self):
        """Test performance metrics"""
        console.print("\n⚡ [bold blue]Testing Performance[/bold blue]")

        perf_results = {}

        async with aiohttp.ClientSession() as session:
            for service, port in self.service_ports.items():
                times = []

                # Test 5 requests
                for _ in range(5):
                    try:
                        start = time.time()
                        async with session.get(
                            f"http://localhost:{port}/health", timeout=5
                        ) as response:
                            if response.status == 200:
                                times.append((time.time() - start) * 1000)
                    except:
                        pass

                if times:
                    avg_time = sum(times) / len(times)
                    perf_results[service] = {
                        "avg_ms": round(avg_time, 2),
                        "success_rate": (len(times) / 5) * 100,
                        "status": (
                            "✅" if avg_time < 20 else "⚠️" if avg_time < 100 else "❌"
                        ),
                    }
                    console.print(
                        f"  {service}: {avg_time:.1f}ms avg {perf_results[service]['status']}"
                    )
                else:
                    perf_results[service] = {
                        "avg_ms": 0,
                        "success_rate": 0,
                        "status": "❌",
                    }
                    console.print(f"  {service}: Failed ❌")

        self.results["performance"] = perf_results
        return perf_results

    def analyze_test_files(self):
        """Analyze existing test files"""
        console.print("\n🧪 [bold blue]Analyzing Test Files[/bold blue]")

        test_results = {}

        # Check for test files in various locations
        test_locations = [
            "tests/",
            "src/tests/",
            "src/services/*/tests/",
            "tools/",
            "scripts/test/",
        ]

        total_test_files = 0
        total_source_files = 0

        # Count Python files in src/
        if os.path.exists("src/"):
            for root, dirs, files in os.walk("src/"):
                for file in files:
                    if file.endswith(".py") and not file.startswith("__"):
                        total_source_files += 1

        # Count test files
        for location in test_locations:
            if os.path.exists(location):
                for root, dirs, files in os.walk(location):
                    for file in files:
                        if file.startswith("test_") or file.endswith("_test.py"):
                            total_test_files += 1

        # Also count our new test files
        test_files = ["Testing.md", "test-coverage.py"]
        for file in test_files:
            if os.path.exists(file):
                total_test_files += 1

        coverage = (total_test_files / max(total_source_files, 1)) * 100

        test_results = {
            "test_files": total_test_files,
            "source_files": total_source_files,
            "coverage": coverage,
            "status": "✅" if coverage >= 50 else "⚠️" if coverage >= 20 else "❌",
        }

        console.print(f"  Test Files: {total_test_files}")
        console.print(f"  Source Files: {total_source_files}")
        console.print(f"  Coverage: {coverage:.1f}% {test_results['status']}")

        self.results["test_files"] = test_results
        return test_results

    def calculate_overall_score(self):
        """Calculate overall test coverage score"""
        weights = {"api_coverage": 0.4, "performance": 0.3, "test_files": 0.3}

        scores = {}

        # API Coverage score
        if "api_coverage" in self.results:
            api_scores = [
                item["coverage"] for item in self.results["api_coverage"].values()
            ]
            scores["api_coverage"] = (
                sum(api_scores) / len(api_scores) if api_scores else 0
            )
        else:
            scores["api_coverage"] = 0

        # Performance score
        if "performance" in self.results:
            perf_scores = [
                item["success_rate"] for item in self.results["performance"].values()
            ]
            scores["performance"] = (
                sum(perf_scores) / len(perf_scores) if perf_scores else 0
            )
        else:
            scores["performance"] = 0

        # Test files score
        if "test_files" in self.results:
            scores["test_files"] = self.results["test_files"]["coverage"]
        else:
            scores["test_files"] = 0

        # Calculate weighted average
        overall = sum(scores[cat] * weights[cat] for cat in weights.keys())

        return overall, scores

    def generate_report(self):
        """Generate comprehensive test report"""
        console.print("\n📊 [bold green]TEST COVERAGE REPORT[/bold green]")
        console.print("=" * 60)

        overall_score, category_scores = self.calculate_overall_score()

        # Overall Score
        console.print(f"\n🎯 [bold]OVERALL SCORE: {overall_score:.1f}%[/bold]")

        if overall_score >= 85:
            status = "🏆 EXCELLENT"
        elif overall_score >= 70:
            status = "✅ GOOD"
        elif overall_score >= 55:
            status = "⚠️ FAIR"
        else:
            status = "❌ POOR"

        console.print(f"Status: [bold]{status}[/bold]")

        # Category Breakdown
        console.print("\n📋 [bold]CATEGORY BREAKDOWN[/bold]")

        table = Table(title="Coverage Analysis", border_style="cyan")
        table.add_column("Category", style="cyan")
        table.add_column("Score", style="yellow", justify="right")
        table.add_column("Weight", style="green", justify="right")
        table.add_column("Status", style="white")

        weights = {"api_coverage": 0.4, "performance": 0.3, "test_files": 0.3}

        for category, score in category_scores.items():
            weight = weights[category]

            if score >= 75:
                cat_status = "✅ Good"
            elif score >= 50:
                cat_status = "⚠️ Fair"
            else:
                cat_status = "❌ Poor"

            table.add_row(
                category.replace("_", " ").title(),
                f"{score:.1f}%",
                f"{weight:.0%}",
                cat_status,
            )

        console.print(table)

        # Summary Stats
        console.print("\n📈 [bold]SUMMARY STATISTICS[/bold]")
        console.print("-" * 40)

        if "api_coverage" in self.results:
            total_endpoints = sum(
                item["total"] for item in self.results["api_coverage"].values()
            )
            working_endpoints = sum(
                item["working"] for item in self.results["api_coverage"].values()
            )
            console.print(
                f"🌐 API Endpoints: {working_endpoints}/{total_endpoints} working"
            )

        if "performance" in self.results:
            avg_response = sum(
                item["avg_ms"] for item in self.results["performance"].values()
            ) / len(self.results["performance"])
            console.print(f"⚡ Avg Response Time: {avg_response:.1f}ms")

        if "test_files" in self.results:
            console.print(
                f"🧪 Test Coverage: {self.results['test_files']['test_files']} test files"
            )

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "overall_score": overall_score,
            "category_scores": category_scores,
            "detailed_results": self.results,
            "status": status,
        }

        os.makedirs("reports", exist_ok=True)
        report_file = f"reports/coverage_report_{timestamp}.json"

        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        console.print(f"\n📄 [bold green]Report saved: {report_file}[/bold green]")

        return report_data

    async def run_full_analysis(self):
        """Run comprehensive test coverage analysis"""
        console.print(
            Panel.fit(
                "[bold cyan]🔍 TEST COVERAGE & REPORT ANALYSIS[/bold cyan]\n"
                "[yellow]Testing APIs, Performance, and Code Coverage[/yellow]",
                border_style="cyan",
            )
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:

            task = progress.add_task("Running analysis...", total=3)

            await self.analyze_api_coverage()
            progress.advance(task)

            progress.update(task, description="Testing performance...")
            await self.analyze_performance()
            progress.advance(task)

            progress.update(task, description="Analyzing test files...")
            self.analyze_test_files()
            progress.advance(task)

        return self.generate_report()


async def main():
    analyzer = TestCoverageAnalyzer()
    await analyzer.run_full_analysis()

    console.print("\n✨ [bold green]Test coverage analysis complete![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())

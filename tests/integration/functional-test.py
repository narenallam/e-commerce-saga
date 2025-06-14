#!/usr/bin/env python3
"""
Simple Functional Test for E-Commerce Saga System
"""

import asyncio
import aiohttp
import time
import subprocess
from rich.console import Console
from rich.table import Table

console = Console()


async def test_health_endpoints():
    """Test all service health endpoints"""
    console.print("🧪 [bold blue]Testing Service Health Endpoints[/bold blue]")

    services = {
        "order-service": 8000,
        "inventory-service": 8001,
        "payment-service": 8002,
        "shipping-service": 8003,
        "notification-service": 8004,
        "saga-coordinator": 9000,
    }

    results = []

    async with aiohttp.ClientSession() as session:
        for service, port in services.items():
            try:
                url = f"http://localhost:{port}/health"
                start_time = time.time()
                async with session.get(url, timeout=5) as response:
                    duration = time.time() - start_time
                    if response.status == 200:
                        results.append(
                            (service, "✅ Healthy", f"{duration*1000:.1f}ms")
                        )
                    else:
                        results.append(
                            (
                                service,
                                f"❌ HTTP {response.status}",
                                f"{duration*1000:.1f}ms",
                            )
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
    console.print(
        f"\n📊 Health Summary: {healthy_count}/{len(services)} services healthy"
    )

    return healthy_count == len(services)


async def test_database_connectivity():
    """Test database connectivity and data"""
    console.print("\n🧪 [bold blue]Testing Database Connectivity[/bold blue]")

    try:
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client.ecommerce_saga

        # Check collections
        collections = ["customers", "inventory", "orders", "payments", "notifications"]
        collection_counts = {}

        for collection_name in collections:
            try:
                count = await db[collection_name].count_documents({})
                collection_counts[collection_name] = count
                console.print(f"  ✅ {collection_name}: {count} documents")
            except Exception as e:
                console.print(f"  ❌ {collection_name}: {str(e)}")
                collection_counts[collection_name] = 0

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


def test_data_consistency():
    """Test data consistency"""
    console.print("\n🧪 [bold blue]Testing Data Consistency[/bold blue]")

    try:
        result = subprocess.run(
            ["python", "tools/data_consistency_checker.py"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            console.print("  ✅ Data consistency check passed")
            console.print("  📊 No critical issues found")
            return True
        else:
            console.print("  ⚠️ Data consistency issues detected")
            lines = result.stdout.split("\n")[:5]  # Show first 5 lines
            for line in lines:
                if line.strip():
                    console.print(f"    {line}")
            return False

    except subprocess.TimeoutExpired:
        console.print("  ⏰ Data consistency check timed out")
        return False
    except Exception as e:
        console.print(f"  ❌ Exception: {str(e)}")
        return False


async def main():
    console.print("[bold cyan]🧪 E-Commerce Saga Quick Functional Test[/bold cyan]")
    console.print("=" * 60)

    # Run tests
    health_passed = await test_health_endpoints()
    db_passed = await test_database_connectivity()
    consistency_passed = test_data_consistency()

    # Summary
    console.print("\n🎯 [bold green]Test Summary[/bold green]")
    console.print("=" * 40)

    tests = [
        ("Service Health", health_passed),
        ("Database Connectivity", db_passed),
        ("Data Consistency", consistency_passed),
    ]

    passed_count = sum(1 for _, passed in tests if passed)

    for test_name, passed in tests:
        status = "✅ PASSED" if passed else "❌ FAILED"
        console.print(f"  {test_name}: {status}")

    console.print(f"\nOverall: {passed_count}/{len(tests)} tests passed")

    if passed_count == len(tests):
        console.print(
            "\n🏆 [bold green]ALL TESTS PASSED! System is healthy.[/bold green]"
        )
    elif passed_count >= len(tests) * 0.7:
        console.print(
            "\n✅ [bold yellow]MOSTLY HEALTHY with minor issues[/bold yellow]"
        )
    else:
        console.print("\n❌ [bold red]MULTIPLE ISSUES DETECTED[/bold red]")


if __name__ == "__main__":
    asyncio.run(main())

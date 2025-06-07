#!/usr/bin/env python3

import requests
import time
import sys
from typing import Dict, List
import logging
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Rich console
console = Console()

# Service configurations with fallback endpoints
SERVICES = {
    "order-service": {
        "primary": "http://localhost:8000/health",
        "fallback": "http://localhost:8000/",
    },
    "inventory-service": {
        "primary": "http://localhost:8001/health",
        "fallback": "http://localhost:8001/",
    },
    "payment-service": {
        "primary": "http://localhost:8002/health",
        "fallback": "http://localhost:8002/",
    },
    "shipping-service": {
        "primary": "http://localhost:8003/health",
        "fallback": "http://localhost:8003/",
    },
    "notification-service": {
        "primary": "http://localhost:8004/health",
        "fallback": "http://localhost:8004/",
    },
}


def check_service_health(
    service_name: str, endpoints: Dict[str, str], timeout: int = 5
) -> Dict:
    """Check the health of a single service with fallback endpoint."""
    # Try primary endpoint first
    try:
        start_time = time.time()
        response = requests.get(endpoints["primary"], timeout=timeout)
        response_time = (time.time() - start_time) * 1000

        if response.status_code == 200:
            return {
                "status": "healthy",
                "status_code": response.status_code,
                "response_time": f"{response_time:.2f}ms",
                "details": response.json(),
                "endpoint": "primary",
            }
    except requests.exceptions.RequestException:
        pass

    # Try fallback endpoint
    try:
        start_time = time.time()
        response = requests.get(endpoints["fallback"], timeout=timeout)
        response_time = (time.time() - start_time) * 1000

        if response.status_code == 200:
            return {
                "status": "healthy",
                "status_code": response.status_code,
                "response_time": f"{response_time:.2f}ms",
                "details": response.json(),
                "endpoint": "fallback",
            }
        else:
            return {
                "status": "unhealthy",
                "status_code": response.status_code,
                "response_time": f"{response_time:.2f}ms",
                "details": f"HTTP {response.status_code}",
                "endpoint": "fallback",
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "unhealthy",
            "status_code": None,
            "response_time": None,
            "details": str(e),
            "endpoint": "both failed",
        }


def display_health_status(results: Dict[str, Dict]):
    """Display health check results in a formatted table."""
    table = Table(title="Service Health Status")

    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Response Time", style="yellow")
    table.add_column("Endpoint", style="magenta")
    table.add_column("Details", style="blue")

    for service, result in results.items():
        status_color = "green" if result["status"] == "healthy" else "red"
        table.add_row(
            service,
            f"[{status_color}]{result['status']}[/{status_color}]",
            result["response_time"] or "N/A",
            result.get("endpoint", "N/A"),
            str(result["details"]) if result["details"] else "N/A",
        )

    console.print(table)


def main():
    console.print("[bold blue]🔍 Starting health check for all services...[/bold blue]")

    results = {}
    with Progress() as progress:
        task = progress.add_task("[cyan]Checking services...", total=len(SERVICES))

        for service_name, endpoints in SERVICES.items():
            results[service_name] = check_service_health(service_name, endpoints)
            progress.update(task, advance=1)

    display_health_status(results)

    # Check if all services are healthy
    all_healthy = all(result["status"] == "healthy" for result in results.values())
    if not all_healthy:
        console.print("[bold red]❌ Some services are unhealthy![/bold red]")
        sys.exit(1)
    else:
        console.print("[bold green]✅ All services are healthy![/bold green]")


if __name__ == "__main__":
    main()

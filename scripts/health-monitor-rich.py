#!/usr/bin/env python3

import subprocess
import json
import time
import sys
from typing import Dict, List, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.columns import Columns
from rich import box
import requests

# Initialize Rich console
console = Console()


def run_kubectl_command(cmd: str) -> List[Dict]:
    """Run kubectl command and return JSON output."""
    try:
        result = subprocess.run(cmd.split(), capture_output=True, text=True, check=True)
        if result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            return [line.split() for line in lines if line.strip()]
        return []
    except subprocess.CalledProcessError:
        return []


def get_pod_status() -> Tuple[int, int]:
    """Get running and total pod counts."""
    pods = run_kubectl_command("kubectl get pods -n e-commerce-saga --no-headers")
    total_pods = len(pods)
    running_pods = sum(1 for pod in pods if len(pod) > 2 and pod[2] == "Running")
    return running_pods, total_pods


def create_deployment_table() -> Table:
    """Create service deployment status table."""
    table = Table(title="🔄 SERVICE DEPLOYMENT STATUS", box=box.ROUNDED)

    table.add_column("SERVICE", style="cyan", no_wrap=True)
    table.add_column("DESIRED", style="yellow", justify="center")
    table.add_column("CURRENT", style="blue", justify="center")
    table.add_column("READY", style="green", justify="center")
    table.add_column("HEALTH", style="bright_green")

    deployments = run_kubectl_command(
        "kubectl get deployments -n e-commerce-saga "
        "--no-headers -o custom-columns="
        "NAME:.metadata.name,"
        "DESIRED:.spec.replicas,"
        "CURRENT:.status.replicas,"
        "READY:.status.readyReplicas"
    )

    for deployment in deployments:
        if len(deployment) >= 4:
            name, desired, current, ready = deployment[:4]
            if ready == desired:
                health = "[green]✅ Healthy[/green]"
            else:
                health = "[red]⚠️  Scaling[/red]"

            table.add_row(name, desired, current, ready, health)

    return table


def create_pod_table() -> Table:
    """Create container status table."""
    table = Table(title="📦 CONTAINER STATUS", box=box.ROUNDED)

    table.add_column("POD NAME", style="cyan", no_wrap=False)
    table.add_column("STATUS", style="green", justify="center")
    table.add_column("RESTARTS", style="yellow", justify="center")
    table.add_column("UPTIME", style="blue")

    pods = run_kubectl_command(
        "kubectl get pods -n e-commerce-saga "
        "--no-headers -o custom-columns="
        "NAME:.metadata.name,"
        "STATUS:.status.phase,"
        "RESTARTS:.status.containerStatuses[0].restartCount,"
        "AGE:.status.startTime"
    )

    for pod in pods:
        if len(pod) >= 4:
            name, status, restarts, start_time = pod[:4]

            # Format age
            if "T" in start_time:
                age_formatted = start_time.split("T")[0].split("-")[1:3]
                age_display = "/".join(age_formatted)
            else:
                age_display = start_time

            # Status with emoji
            if status == "Running":
                status_display = "[green]🟢 Running[/green]"
                pod_name_display = f"[bright_cyan]{name}[/bright_cyan]"
            elif status == "Pending":
                status_display = "[yellow]🟡 Pending[/yellow]"
                pod_name_display = f"[yellow]{name}[/yellow]"
            else:
                status_display = "[red]🔴 Error[/red]"
                pod_name_display = f"[red]{name}[/red]"

            table.add_row(pod_name_display, status_display, restarts, age_display)

    return table


def create_service_table() -> Table:
    """Create service connectivity table."""
    table = Table(title="🌐 SERVICE CONNECTIVITY", box=box.ROUNDED)

    table.add_column("SERVICE", style="cyan", no_wrap=True)
    table.add_column("PORT", style="yellow", justify="center")
    table.add_column("ENDPOINTS", style="blue")
    table.add_column("STATUS", style="green")

    services = run_kubectl_command("kubectl get svc -n e-commerce-saga --no-headers")

    for service in services:
        if len(service) >= 5:
            name, svc_type, cluster_ip, external_ip, ports = service[:5]
            port_clean = ports.split("/")[0] if "/" in ports else ports

            # Get endpoint count
            try:
                endpoints_result = subprocess.run(
                    [
                        "kubectl",
                        "get",
                        "endpoints",
                        name,
                        "-n",
                        "e-commerce-saga",
                        "-o",
                        "jsonpath={.subsets[0].addresses[*].ip}",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                endpoint_count = (
                    len(endpoints_result.stdout.strip().split())
                    if endpoints_result.stdout.strip()
                    else 0
                )
            except:
                endpoint_count = 0

            if endpoint_count > 0:
                service_display = f"[green]🌟 {name}[/green]"
                endpoints_display = f"[blue]{endpoint_count} ready[/blue]"
                status_display = "[green]Connected[/green]"
            else:
                service_display = f"[red]💥 {name}[/red]"
                endpoints_display = "[red]no endpoints[/red]"
                status_display = "[red]Disconnected[/red]"

            table.add_row(
                service_display, port_clean, endpoints_display, status_display
            )

    return table


def create_health_check_table() -> Table:
    """Create application health check table."""
    table = Table(title="🩺 APPLICATION HEALTH CHECKS", box=box.ROUNDED)

    table.add_column("SERVICE", style="cyan")
    table.add_column("STATUS", style="green")
    table.add_column("NOTE", style="yellow")

    # Check if port forwarding is active
    try:
        result = subprocess.run(
            ["pgrep", "-f", "kubectl port-forward.*e-commerce-saga"],
            capture_output=True,
            text=True,
        )
        port_forward_active = result.returncode == 0
    except:
        port_forward_active = False

    services = [
        "order-service",
        "inventory-service",
        "payment-service",
        "shipping-service",
        "notification-service",
        "saga-coordinator",
    ]

    if not port_forward_active:
        for service in services:
            table.add_row(
                service, "[yellow]Unknown[/yellow]", "[blue]Need port-forward[/blue]"
            )

    return table, port_forward_active


def create_overview_panel(running_pods: int, total_pods: int) -> Panel:
    """Create application overview panel."""
    if total_pods > 0:
        # Create visual dots for pod status
        dots = "".join(
            ["[green]●[/green]"] * running_pods
            + ["[red]●[/red]"] * (total_pods - running_pods)
        )
        status_text = f"[green]🚀 Application Status: {running_pods}/{total_pods} services running[/green] {dots}"
    else:
        status_text = (
            "[yellow]⚠️  No services deployed - run 'make deploy' first[/yellow]"
        )

    return Panel(status_text, title="📊 APPLICATION OVERVIEW", box=box.ROUNDED)


def main():
    """Main health monitoring function."""
    console.clear()

    # Header
    console.print(
        Panel.fit(
            "[bold cyan]🩺 SERVICE HEALTH & APPLICATION STATUS[/bold cyan]",
            box=box.DOUBLE,
        )
    )
    console.print()

    # Get pod status
    running_pods, total_pods = get_pod_status()

    # Application overview
    overview_panel = create_overview_panel(running_pods, total_pods)
    console.print(overview_panel)
    console.print()

    # Service deployment status
    deployment_table = create_deployment_table()
    console.print(deployment_table)
    console.print()

    # Container status
    pod_table = create_pod_table()
    console.print(pod_table)
    console.print()

    # Service connectivity
    service_table = create_service_table()
    console.print(service_table)
    console.print()

    # Application health checks
    health_table, port_forward_active = create_health_check_table()

    if port_forward_active:
        console.print(
            "[green]✅ Port forwarding is active - performing health checks...[/green]"
        )
        console.print()

        # Run the existing Python health check
        try:
            result = subprocess.run(
                [sys.executable, "scripts/monitoring/check_health.py"],
                env={"PYTHONPATH": "src"},
                cwd=".",
                capture_output=False,
            )
        except Exception as e:
            console.print(f"[red]⚠️  Health check script failed: {e}[/red]")
    else:
        console.print(
            "[yellow]⚠️  Port forwarding not active - cannot perform application health checks[/yellow]"
        )
        console.print(
            "[blue]💡 Run 'make port-forward' to enable detailed health checking[/blue]"
        )
        console.print()
        console.print(health_table)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import subprocess
import time
import sys
import signal
from datetime import datetime
from typing import Dict, List, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from rich import box
from rich.columns import Columns

# Initialize Rich console
console = Console()


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    console.print("\n[yellow]👋 Monitoring stopped by user[/yellow]")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def run_kubectl_command(cmd: str) -> List[List[str]]:
    """Run kubectl command and return parsed output."""
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


def create_overview_panel(running_pods: int, total_pods: int) -> Panel:
    """Create pod overview panel."""
    if total_pods > 0:
        # Create visual dots for pod status
        dots = "".join(
            ["[green]●[/green]"] * running_pods
            + ["[red]●[/red]"] * (total_pods - running_pods)
        )
        status_text = (
            f"[green]🚀 Running: {running_pods}/{total_pods} pods[/green] {dots}"
        )
    else:
        status_text = "[yellow]⚠️ No pods found[/yellow]"

    return Panel(status_text, title="📦 POD STATUS OVERVIEW", box=box.ROUNDED)


def create_pods_table() -> Table:
    """Create real-time pods status table."""
    table = Table(title="📋 POD STATUS", box=box.ROUNDED, show_lines=True)

    table.add_column("POD NAME", style="cyan", no_wrap=False, max_width=35)
    table.add_column("STATUS", style="green", justify="center", width=12)
    table.add_column("RESTARTS", style="yellow", justify="center", width=9)
    table.add_column("AGE", style="blue", width=8)

    pods = run_kubectl_command("kubectl get pods -n e-commerce-saga --no-headers")

    for pod in pods:
        if len(pod) >= 5:
            name, ready, status, restarts, age = pod[:5]

            # Format status with emoji
            if status == "Running":
                status_display = "[green]🟢 Running[/green]"
                name_display = f"[bright_cyan]{name}[/bright_cyan]"
            elif status == "Pending":
                status_display = "[yellow]🟡 Pending[/yellow]"
                name_display = f"[yellow]{name}[/yellow]"
            else:
                status_display = "[red]🔴 Error[/red]"
                name_display = f"[red]{name}[/red]"

            table.add_row(name_display, status_display, restarts, f"[blue]{age}[/blue]")

    return table


def create_deployments_table() -> Table:
    """Create deployment health table."""
    table = Table(title="🔄 DEPLOYMENT HEALTH", box=box.ROUNDED, show_lines=True)

    table.add_column("DEPLOYMENT", style="cyan", max_width=20)
    table.add_column("DESIRED", style="yellow", justify="center", width=8)
    table.add_column("READY", style="green", justify="center", width=7)
    table.add_column("STATUS", style="bright_green", width=12)

    deployments = run_kubectl_command(
        "kubectl get deployments -n e-commerce-saga --no-headers"
    )

    for deployment in deployments:
        if len(deployment) >= 5:
            name, ready_info, up_to_date, available, age = deployment[:5]

            # Parse ready info (format: "current/desired")
            if "/" in ready_info:
                current, desired = ready_info.split("/")
            else:
                current = desired = ready_info

            # Format status
            if current == desired:
                status_display = "[green]✅ Healthy[/green]"
                name_display = f"[green]{name}[/green]"
                ready_display = f"[green]{current}[/green]"
            else:
                status_display = "[red]⚠️ Scaling[/red]"
                name_display = f"[yellow]{name}[/yellow]"
                ready_display = f"[red]{current}[/red]"

            table.add_row(
                name_display,
                f"[yellow]{desired}[/yellow]",
                ready_display,
                status_display,
            )

    return table


def create_services_table() -> Table:
    """Create service connectivity table."""
    table = Table(title="🌐 SERVICE CONNECTIVITY", box=box.ROUNDED, show_lines=True)

    table.add_column("SERVICE", style="cyan", max_width=20)
    table.add_column("PORT", style="blue", justify="center", width=6)
    table.add_column("ENDPOINTS", style="yellow", width=10)
    table.add_column("STATUS", style="green", width=11)

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
                endpoints_display = f"[green]{endpoint_count} ready[/green]"
                status_display = "[green]Connected[/green]"
            else:
                service_display = f"[red]💥 {name}[/red]"
                endpoints_display = "[red]no endpoints[/red]"
                status_display = "[red]Disconnected[/red]"

            table.add_row(
                service_display,
                f"[blue]{port_clean}[/blue]",
                endpoints_display,
                status_display,
            )

    return table


def create_resources_table() -> Table:
    """Create resource usage table."""
    table = Table(title="💻 RESOURCE USAGE", box=box.ROUNDED, show_lines=True)

    table.add_column("POD", style="cyan", max_width=30)
    table.add_column("CPU", style="green", justify="right", width=8)
    table.add_column("MEMORY", style="magenta", justify="right", width=8)

    # Check if metrics server is available
    try:
        result = subprocess.run(
            ["kubectl", "top", "pods", "-n", "e-commerce-saga", "--no-headers"],
            capture_output=True,
            text=True,
            check=True,
        )

        lines = result.stdout.strip().split("\n")[:8]  # Show top 8 pods
        for line in lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 3:
                    name, cpu, memory = parts[:3]
                    table.add_row(
                        f"[cyan]📊 {name[:25]}[/cyan]",
                        f"[green]{cpu}[/green]",
                        f"[magenta]{memory}[/magenta]",
                    )
    except:
        table.add_row(
            "[yellow]⚠️ Metrics not available[/yellow]",
            "[gray]--[/gray]",
            "[red]install metrics[/red]",
        )

    return table


def main():
    """Main monitoring function with clean scrolling updates."""
    console.clear()

    # Print header only once at startup
    console.print(
        Panel.fit(
            "[bold cyan]🕐 REAL-TIME CLUSTER MONITOR[/bold cyan]",
            box=box.DOUBLE,
        )
    )
    console.print("[dim]💡 Press Ctrl+C to stop | 🔄 Updates every 5 seconds[/dim]")
    console.print()

    try:
        update_count = 0
        while True:
            update_count += 1
            timestamp = datetime.now().strftime("%H:%M:%S")

            # Get current status
            running_pods, total_pods = get_pod_status()

            # Print update header with timestamp
            console.print(f"[bold]📊 Update #{update_count} - {timestamp}[/bold]")
            console.print()

            # Overview
            console.print(create_overview_panel(running_pods, total_pods))
            console.print()

            # All Pods Table
            console.print(create_pods_table())
            console.print()

            # Deployment table
            console.print(create_deployments_table())
            console.print()

            # Service and resource tables side by side
            console.print(
                Columns(
                    [
                        Panel(create_services_table(), padding=(0, 1)),
                        Panel(create_resources_table(), padding=(0, 1)),
                    ],
                    equal=True,
                )
            )

            console.print()
            console.print("[dim]" + "─" * 80 + "[/dim]")  # Separator line
            console.print()

            time.sleep(5)

    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Monitoring stopped by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()

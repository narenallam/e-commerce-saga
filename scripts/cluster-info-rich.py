#!/usr/bin/env python3

import subprocess
import json
import time
import sys
from typing import Dict, List, Tuple, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.columns import Columns
from rich import box
from rich.progress import Progress

# Initialize Rich console
console = Console()


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


def create_cluster_overview_panel() -> Panel:
    """Create cluster overview panel."""
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info", "--short"],
            capture_output=True,
            text=True,
            check=True,
        )

        cluster_info = []
        for line in result.stdout.strip().split("\n"):
            if "running at" in line:
                cluster_info.append(f"[green]✅ {line}[/green]")
            else:
                cluster_info.append(f"[blue]ℹ️  {line}[/blue]")

        info_text = "\n".join(cluster_info)
    except:
        info_text = "[red]❌ Unable to retrieve cluster information[/red]"

    return Panel(info_text, title="📊 CLUSTER OVERVIEW", box=box.ROUNDED)


def create_nodes_table() -> Table:
    """Create cluster nodes table."""
    table = Table(title="🏠 CLUSTER NODES & ARCHITECTURE", box=box.ROUNDED)

    table.add_column("NODE", style="cyan", no_wrap=True)
    table.add_column("STATUS", style="green", justify="center")
    table.add_column("ROLE", style="yellow")
    table.add_column("VERSION", style="blue")
    table.add_column("OS", style="magenta")
    table.add_column("ARCH", style="bright_blue")

    nodes = run_kubectl_command(
        "kubectl get nodes -o custom-columns="
        "NAME:.metadata.name,"
        "STATUS:.status.conditions[3].type,"
        "ROLES:.metadata.labels.node-role\\.kubernetes\\.io/control-plane,"
        "VERSION:.status.nodeInfo.kubeletVersion,"
        "OS:.status.nodeInfo.operatingSystem,"
        "ARCH:.status.nodeInfo.architecture --no-headers"
    )

    for node in nodes:
        if len(node) >= 6:
            name, status, role, version, os, arch = node[:6]

            # Format role
            if role == "<none>":
                role_display = "[blue]🔧 worker[/blue]"
            else:
                role_display = "[yellow]👑 control-plane[/yellow]"

            # Format status
            if status == "Ready":
                status_display = "[green]⭐ Ready[/green]"
                name_display = f"[green]{name}[/green]"
            else:
                status_display = "[red]❌ Not Ready[/red]"
                name_display = f"[red]{name}[/red]"

            table.add_row(
                name_display,
                status_display,
                role_display,
                f"[blue]{version}[/blue]",
                f"[magenta]{os}[/magenta]",
                f"[bright_blue]{arch}[/bright_blue]",
            )

    return table


def create_node_resources_table() -> Table:
    """Create node resource utilization table."""
    table = Table(title="🏗️ NODE RESOURCE UTILIZATION", box=box.ROUNDED)

    table.add_column("NODE", style="cyan")
    table.add_column("CPU(cores)", style="green", justify="right")
    table.add_column("CPU%", style="yellow", justify="right")
    table.add_column("MEMORY(bytes)", style="blue", justify="right")
    table.add_column("MEMORY%", style="magenta", justify="right")

    # Check if metrics server is available
    try:
        result = subprocess.run(
            ["kubectl", "top", "nodes", "--no-headers"],
            capture_output=True,
            text=True,
            check=True,
        )

        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 5:
                    name, cpu, cpu_pct, memory, memory_pct = parts[:5]
                    table.add_row(
                        f"[cyan]💻 {name}[/cyan]",
                        f"[green]{cpu}[/green]",
                        f"[yellow]{cpu_pct}[/yellow]",
                        f"[blue]{memory}[/blue]",
                        f"[magenta]{memory_pct}[/magenta]",
                    )
    except:
        table.add_row(
            "[yellow]⚠️  Metrics server not available[/yellow]",
            "[gray]--[/gray]",
            "[gray]--[/gray]",
            "[gray]--[/gray]",
            "[red]Run 'make metrics' to install[/red]",
        )

    return table


def create_pod_distribution_table() -> Table:
    """Create pod distribution across nodes table."""
    table = Table(title="📦 POD DISTRIBUTION ACROSS NODES", box=box.ROUNDED)

    table.add_column("NODE", style="cyan")
    table.add_column("POD COUNT", style="green", justify="center")
    table.add_column("VISUAL DISTRIBUTION", style="yellow")

    # Get pod distribution
    try:
        result = subprocess.run(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                "e-commerce-saga",
                "-o",
                "wide",
                "--no-headers",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        node_pods = {}
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 7:
                    node = parts[6]  # Node is typically the 7th column
                    node_pods[node] = node_pods.get(node, 0) + 1

        for node, count in node_pods.items():
            visual_dots = "[yellow]" + "●" * count + "[/yellow]"
            table.add_row(
                f"[cyan]🏠 {node}[/cyan]", f"[green]{count} pods[/green]", visual_dots
            )

        if not node_pods:
            table.add_row(
                "[yellow]⚠️  No pods found[/yellow]",
                "[gray]0[/gray]",
                "[gray]No distribution[/gray]",
            )

    except:
        table.add_row(
            "[red]❌ Unable to get pod distribution[/red]",
            "[gray]--[/gray]",
            "[gray]--[/gray]",
        )

    return table


def create_deployment_scaling_table() -> Table:
    """Create deployment scaling & strategy table."""
    table = Table(title="🔄 DEPLOYMENT SCALING & STRATEGY", box=box.ROUNDED)

    table.add_column("DEPLOYMENT", style="cyan")
    table.add_column("REPLICAS", style="yellow", justify="center")
    table.add_column("READY", style="green", justify="center")
    table.add_column("STRATEGY", style="blue")
    table.add_column("PRIORITY", style="magenta")

    deployments = run_kubectl_command(
        "kubectl get deployments -n e-commerce-saga "
        "-o custom-columns="
        "NAME:.metadata.name,"
        "REPLICAS:.spec.replicas,"
        "READY:.status.readyReplicas,"
        "STRATEGY:.spec.strategy.type --no-headers"
    )

    for deployment in deployments:
        if len(deployment) >= 4:
            name, replicas, ready, strategy = deployment[:4]

            # Determine priority based on service name
            if any(x in name for x in ["order", "payment", "saga"]):
                priority = "[red]🔥 High[/red]"
            elif any(x in name for x in ["inventory", "shipping"]):
                priority = "[yellow]⚡ Medium[/yellow]"
            elif "notification" in name:
                priority = "[blue]💎 Low[/blue]"
            else:
                priority = "[white]⭐ Standard[/white]"

            # Format status
            if ready == replicas:
                status_icon = "[green]✅[/green]"
                ready_display = f"[green]{ready}[/green]"
                name_display = f"[green]{name}[/green]"
            else:
                status_icon = "[red]⚠️[/red]"
                ready_display = f"[red]{ready}[/red]"
                name_display = f"[yellow]{name}[/yellow]"

            table.add_row(
                f"{status_icon} {name_display}",
                f"[yellow]{replicas}[/yellow]",
                ready_display,
                f"[blue]{strategy}[/blue]",
                priority,
            )

    return table


def create_network_topology_table() -> Table:
    """Create network topology & services table."""
    table = Table(title="🌐 NETWORK TOPOLOGY & SERVICES", box=box.ROUNDED)

    table.add_column("SERVICE", style="cyan")
    table.add_column("TYPE", style="magenta")
    table.add_column("CLUSTER-IP", style="yellow")
    table.add_column("PORT", style="blue", justify="center")
    table.add_column("TARGET", style="green", justify="center")
    table.add_column("ENDPOINTS", style="bright_green")

    services = run_kubectl_command(
        "kubectl get svc -n e-commerce-saga "
        "-o custom-columns="
        "NAME:.metadata.name,"
        "TYPE:.spec.type,"
        "CLUSTER-IP:.spec.clusterIP,"
        "PORT:.spec.ports[0].port,"
        "TARGET-PORT:.spec.ports[0].targetPort --no-headers"
    )

    for service in services:
        if len(service) >= 5:
            name, svc_type, cluster_ip, port, target_port = service[:5]

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
            else:
                service_display = f"[red]💥 {name}[/red]"
                endpoints_display = "[red]no endpoints[/red]"

            table.add_row(
                service_display,
                f"[magenta]{svc_type}[/magenta]",
                f"[yellow]{cluster_ip}[/yellow]",
                f"[blue]{port}[/blue]",
                f"[green]{target_port}[/green]",
                endpoints_display,
            )

    return table


def create_storage_table() -> Table:
    """Create storage infrastructure table."""
    table = Table(title="💾 STORAGE INFRASTRUCTURE", box=box.ROUNDED)

    table.add_column("PERSISTENT VOLUME", style="cyan")
    table.add_column("CAPACITY", style="yellow")
    table.add_column("ACCESS MODE", style="blue")
    table.add_column("RECLAIM POLICY", style="magenta")
    table.add_column("STATUS", style="green")

    # Check for persistent volumes
    pvs = run_kubectl_command(
        "kubectl get pv "
        "-o custom-columns="
        "NAME:.metadata.name,"
        "CAPACITY:.spec.capacity.storage,"
        "ACCESS-MODE:.spec.accessModes[0],"
        "RECLAIM-POLICY:.spec.persistentVolumeReclaimPolicy,"
        "STATUS:.status.phase --no-headers"
    )

    if pvs:
        for pv in pvs:
            if len(pv) >= 5:
                name, capacity, access_mode, reclaim_policy, status = pv[:5]

                if status == "Bound":
                    status_display = "[green]💾 Bound[/green]"
                    name_display = f"[green]{name}[/green]"
                else:
                    status_display = f"[red]⚠️ {status}[/red]"
                    name_display = f"[red]{name}[/red]"

                table.add_row(
                    name_display,
                    f"[yellow]{capacity}[/yellow]",
                    f"[blue]{access_mode}[/blue]",
                    f"[magenta]{reclaim_policy}[/magenta]",
                    status_display,
                )
    else:
        table.add_row(
            "[yellow]⚠️ No persistent volumes found[/yellow]",
            "[gray]--[/gray]",
            "[gray]--[/gray]",
            "[gray]--[/gray]",
            "[gray]--[/gray]",
        )

    return table


def main():
    """Main cluster info function."""
    console.clear()

    # Header
    console.print(
        Panel.fit(
            "[bold cyan]🌐 KUBERNETES CLUSTER INFRASTRUCTURE & TOPOLOGY[/bold cyan]",
            box=box.DOUBLE,
        )
    )
    console.print()

    # Cluster overview
    overview_panel = create_cluster_overview_panel()
    console.print(overview_panel)
    console.print()

    # Nodes table
    nodes_table = create_nodes_table()
    console.print(nodes_table)
    console.print()

    # Node resources
    resources_table = create_node_resources_table()
    console.print(resources_table)
    console.print()

    # Pod distribution
    pod_dist_table = create_pod_distribution_table()
    console.print(pod_dist_table)
    console.print()

    # Deployment scaling
    deployment_table = create_deployment_scaling_table()
    console.print(deployment_table)
    console.print()

    # Network topology
    network_table = create_network_topology_table()
    console.print(network_table)
    console.print()

    # Storage infrastructure
    storage_table = create_storage_table()
    console.print(storage_table)


if __name__ == "__main__":
    main()

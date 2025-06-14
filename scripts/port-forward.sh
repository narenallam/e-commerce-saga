#!/bin/bash

# Kill any existing port-forward processes
pkill -f "kubectl port-forward"

# Function to start port forwarding
start_port_forward() {
    local service=$1
    local local_port=$2
    local remote_port=$3
    echo "Starting port forward for $service on port $local_port"
    kubectl port-forward -n e-commerce-saga svc/$service $local_port:$remote_port &
    sleep 2
}

# Start port forwarding for all services
start_port_forward "order-service" 8000 8000
start_port_forward "inventory-service" 8001 8001
start_port_forward "payment-service" 8002 8002
start_port_forward "shipping-service" 8003 8003
start_port_forward "notification-service" 8004 8004
start_port_forward "saga-coordinator" 9000 9000
start_port_forward "mongodb" 27017 27017
start_port_forward "redis" 6379 6379
start_port_forward "kafka-client" 9092 9092
start_port_forward "zookeeper" 2181 2181

echo "All port forwards are set up. Use 'pkill -f kubectl' to stop all port forwards." 
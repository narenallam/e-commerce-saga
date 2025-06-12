#!/bin/bash

# Make script exit if any command fails
set -e

echo "Building Docker images..."

# Build service images
SERVICES=("order" "inventory" "payment" "shipping" "notification")

for service in "${SERVICES[@]}"; do
  echo "Building $service service..."
  docker build -t e-commerce-saga/$service-service:latest \
    --build-arg SERVICE_DIR=$service \
    -f deployments/docker/Dockerfile .
done

echo "Creating Kubernetes namespace..."
kubectl create namespace e-commerce-saga --dry-run=client -o yaml | kubectl apply -f - --validate=false

echo "Deploying services to Kubernetes..."
kubectl apply -f deployments/kubernetes/k8s-local-deployment.yaml --validate=false

echo "Waiting for pods to be ready..."
kubectl wait --namespace e-commerce-saga \
  --for=condition=ready pod \
  --selector=app=mongodb \
  --timeout=90s

echo "Setting up port forwarding..."
echo "Press Ctrl+C to stop port forwarding"

# Start port forwarding in background
kubectl port-forward -n e-commerce-saga svc/order-service 8000:8000 &
kubectl port-forward -n e-commerce-saga svc/inventory-service 8001:8001 &
kubectl port-forward -n e-commerce-saga svc/payment-service 8002:8002 &
kubectl port-forward -n e-commerce-saga svc/shipping-service 8003:8003 &
kubectl port-forward -n e-commerce-saga svc/notification-service 8004:8004 &

echo "Services are now available at:"
echo "Order Service: http://localhost:8000"
echo "Inventory Service: http://localhost:8001"
echo "Payment Service: http://localhost:8002"
echo "Shipping Service: http://localhost:8003"
echo "Notification Service: http://localhost:8004"

# Wait for user to press Ctrl+C
wait 
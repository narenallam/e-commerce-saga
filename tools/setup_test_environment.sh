#!/bin/bash
# Setup Test Environment for E-commerce Saga

set -e

echo "🚀 Setting up E-commerce Saga test environment..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is required but not installed"
    exit 1
fi

# Check if MongoDB port forwarding is needed
if ! curl -s localhost:27017 &> /dev/null; then
    echo "📡 Setting up MongoDB port forwarding..."
    kubectl port-forward -n e-commerce-saga svc/mongodb 27017:27017 &
    MONGO_PID=$!
    sleep 5
fi

# Check if services are running
echo "🔍 Checking service health..."
services=("order:8000" "inventory:8001" "payment:8002" "shipping:8003" "notification:8004")

for service in "${services[@]}"; do
    name=$(echo $service | cut -d: -f1)
    port=$(echo $service | cut -d: -f2)
    
    if ! curl -s -f http://localhost:$port/health > /dev/null; then
        echo "📡 Setting up $name service port forwarding..."
        kubectl port-forward -n e-commerce-saga svc/$name-service $port:$port &
        sleep 2
    fi
done

echo "⏳ Waiting for services to be ready..."
sleep 10

# Verify all services are healthy
echo "🩺 Running health checks..."
python scripts/health_monitor.py --once

# Generate test data
echo "📊 Generating test data..."
python scripts/test_data_generator.py --reset --customers 20 --products 50 --orders 100

echo "✅ Test environment setup complete!"
echo ""
echo "Available endpoints:"
echo "  Order Service:       http://localhost:8000/docs"
echo "  Inventory Service:   http://localhost:8001/docs" 
echo "  Payment Service:     http://localhost:8002/docs"
echo "  Shipping Service:    http://localhost:8003/docs"
echo "  Notification Service: http://localhost:8004/docs"
echo "  MongoDB:             mongodb://localhost:27017"
echo ""
echo "Test data summary:"
echo "  - 20 customers generated"
echo "  - 50 products generated" 
echo "  - 100 sample orders generated"
echo ""
echo "Run 'python scripts/functional_tests.py' to execute test suite" 
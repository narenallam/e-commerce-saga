#!/bin/bash

# Make script exit if any command fails
set -e

echo "Installing dependencies..."
pip install -r common/requirements.txt

echo "Starting MongoDB..."
podman run -d -p 27017:27017 --name saga-mongodb mongo:latest
sleep 5  # Wait for MongoDB to start

echo "Starting Order Service..."
cd services/order
PYTHONPATH=../.. python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
cd ../..

echo "Starting Inventory Service..."
cd services/inventory
PYTHONPATH=../.. python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload &
cd ../..

echo "Starting Payment Service..."
cd services/payment
PYTHONPATH=../.. python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload &
cd ../..

echo "Starting Shipping Service..."
cd services/shipping
PYTHONPATH=../.. python -m uvicorn main:app --host 0.0.0.0 --port 8003 --reload &
cd ../..

echo "Starting Notification Service..."
cd services/notification
PYTHONPATH=../.. python -m uvicorn main:app --host 0.0.0.0 --port 8004 --reload &
cd ../..

echo "All services started!"
echo "- Order Service: http://localhost:8000"
echo "- Inventory Service: http://localhost:8001"
echo "- Payment Service: http://localhost:8002"
echo "- Shipping Service: http://localhost:8003"
echo "- Notification Service: http://localhost:8004"

echo "Press Ctrl+C to stop all services"
wait 
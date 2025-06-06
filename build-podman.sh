#!/bin/bash

# Make script exit if any command fails
set -e

ROOT_DIR=$(pwd)
SERVICES=("order" "inventory" "payment" "shipping" "notification")

echo "Building base image..."
podman build -t e-commerce-saga-base .

for service in "${SERVICES[@]}"; do
  echo "Building $service service..."

  # Determine port based on service
  case "$service" in
    "order") port="8000" ;;
    "inventory") port="8001" ;;
    "payment") port="8002" ;;
    "shipping") port="8003" ;;
    "notification") port="8004" ;;
  esac

  # Create a temporary Dockerfile for each service
  cat > services/$service/Dockerfile.podman << EOF
FROM localhost/e-commerce-saga-base:latest

# Set service-specific arguments
ENV SERVICE_DIR=$service
ENV PYTHONPATH=/app

# Copy coordinator for order service
$([ "$service" == "order" ] && echo "COPY ../../coordinator /app/coordinator")

# Set the working directory to the service directory
WORKDIR /app/services/$service

# Expose the service port
EXPOSE $port

# Set the entrypoint command
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$port"]
EOF

  # Build the image
  podman build -t e-commerce-saga/$service-service:latest -f services/$service/Dockerfile.podman $ROOT_DIR

  # Clean up
  rm services/$service/Dockerfile.podman
done

echo "All service images built successfully!"
echo "To push to your OpenShift registry, tag and push these images." 
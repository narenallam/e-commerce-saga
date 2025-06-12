#!/bin/bash

# Make script exit if any command fails
set -e

SERVICES=("order" "inventory" "payment" "shipping" "notification")

# Create project if it doesn't exist
if ! oc get project e-commerce-saga &> /dev/null; then
  echo "Creating project 'e-commerce-saga'..."
  oc new-project e-commerce-saga
else
  echo "Project 'e-commerce-saga' already exists."
  oc project e-commerce-saga
fi

# Process each service
for service in "${SERVICES[@]}"; do
  echo "Processing $service service image..."
  
  # Create or replace imagestream if it doesn't exist
  if ! oc get imagestream $service-service -n e-commerce-saga &> /dev/null; then
    echo "Creating imagestream for $service service..."
    oc create imagestream $service-service -n e-commerce-saga
  else
    echo "Imagestream already exists for $service service."
  fi
done

echo "All imagestreams created successfully!"

# Let's also update the Helm deployment to use local image references
echo "Updating Helm deployment..."
helm upgrade --install e-commerce-saga ./helm \
  --namespace e-commerce-saga \
  --set global.environment=production \
  --set global.resources.requests.memory=64Mi \
  --set global.resources.limits.memory=128Mi \
  --set mongodb.persistence.enabled=false \
  --set mongodb.resources.requests.memory=128Mi \
  --set mongodb.resources.limits.memory=256Mi \
  --set order.image.repository=order-service \
  --set order.image.tag=latest \
  --set inventory.image.repository=inventory-service \
  --set inventory.image.tag=latest \
  --set payment.image.repository=payment-service \
  --set payment.image.tag=latest \
  --set shipping.image.repository=shipping-service \
  --set shipping.image.tag=latest \
  --set notification.image.repository=notification-service \
  --set notification.image.tag=latest

echo "Helm deployment updated successfully!"

# Let's check the status of the pods
echo "Checking pod status..."
oc get pods -n e-commerce-saga

echo "Deployment completed! Note: You may need to wait a few minutes for all pods to start."

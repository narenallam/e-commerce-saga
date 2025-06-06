#!/bin/bash

# Make script exit if any command fails
set -e

SERVICES=("order" "inventory" "payment" "shipping" "notification")
REGISTRY="$(oc get route default-route -n openshift-image-registry --template='{{ .spec.host }}')"

# Check if we need to login to OpenShift
if ! oc whoami &> /dev/null; then
  echo "Not logged in to OpenShift. Please login first with:"
  echo "oc login"
  exit 1
fi

# Create project if it doesn't exist
if ! oc get project e-commerce-saga &> /dev/null; then
  echo "Creating project 'e-commerce-saga'..."
  oc new-project e-commerce-saga
else
  echo "Project 'e-commerce-saga' already exists."
fi

# Try a minimal approach with direct OpenShift commands
# Ensure the registry is exposed
echo "Setting up the OpenShift registry..."
oc patch configs.imageregistry.operator.openshift.io/cluster --patch '{"spec":{"defaultRoute":true}}' --type=merge

# Wait for the route to be available
echo "Waiting for registry route to be available..."
sleep 5

# Set up credentials for the registry
token=$(oc whoami -t)
username=$(oc whoami)

for service in "${SERVICES[@]}"; do
  echo "Processing $service service image..."
  
  # Create or update imagestream
  if ! oc get imagestream $service-service &> /dev/null; then
    echo "Creating imagestream for $service service..."
    oc create imagestream $service-service
  fi
  
  echo "Creating or updating deployment configuration..."
  
  # Create or replace deployment
  if oc get deployment $service-service -n e-commerce-saga &> /dev/null; then
    echo "Deployment already exists. Replacing it..."
    oc delete deployment $service-service -n e-commerce-saga
    sleep 2
  fi
  
  oc create deployment $service-service --image=localhost/e-commerce-saga/$service-service:latest -n e-commerce-saga
  
  # Expose the service
  port=""
  case "$service" in 
    "order") port="8000" ;; 
    "inventory") port="8001" ;; 
    "payment") port="8002" ;; 
    "shipping") port="8003" ;; 
    "notification") port="8004" ;; 
  esac
  
  # Delete service if it exists
  if oc get service $service-service -n e-commerce-saga &> /dev/null; then
    echo "Service already exists. Replacing it..."
    oc delete service $service-service -n e-commerce-saga
    sleep 2
  fi
  
  oc expose deployment $service-service --port=$port -n e-commerce-saga
  
  # Delete route if it exists
  if oc get route $service-service -n e-commerce-saga &> /dev/null; then
    echo "Route already exists. Replacing it..."
    oc delete route $service-service -n e-commerce-saga
    sleep 2
  fi
  
  oc create route edge $service-service --service=$service-service -n e-commerce-saga
done

echo "All services deployed to OpenShift!"
echo "You can access the services via the routes:"
oc get routes -n e-commerce-saga 
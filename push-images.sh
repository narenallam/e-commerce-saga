#!/bin/bash

# Make script exit if any command fails
set -e

SERVICES=("order" "inventory" "payment" "shipping" "notification")

# Get registry route
REGISTRY="$(oc get route default-route -n openshift-image-registry --template='{{ .spec.host }}')"

# Login to the registry
echo "Logging in to the OpenShift registry..."
podman login -u kubeadmin -p $(oc whoami -t) $REGISTRY --tls-verify=false

# Create project if it doesn't exist
if ! oc get project e-commerce-saga &> /dev/null; then
  echo "Creating project 'e-commerce-saga'..."
  oc new-project e-commerce-saga
else
  echo "Project 'e-commerce-saga' already exists."
  oc project e-commerce-saga
fi

# Ensure the registry is exposed
echo "Setting up the OpenShift registry..."
oc patch configs.imageregistry.operator.openshift.io/cluster --patch '{"spec":{"defaultRoute":true}}' --type=merge || true

# Process each service
for service in "${SERVICES[@]}"; do
  echo "Processing $service service image..."
  
  # Create imagestream if it doesn't exist
  if ! oc get imagestream $service-service -n e-commerce-saga &> /dev/null; then
    echo "Creating imagestream for $service service..."
    oc create imagestream $service-service -n e-commerce-saga
  fi
  
  # Tag the local image with the OpenShift registry URL
  echo "Tagging $service service image..."
  podman tag localhost/e-commerce-saga/$service-service:latest $REGISTRY/e-commerce-saga/$service-service:latest
  
  # Push the image to the OpenShift registry
  echo "Pushing $service service image to OpenShift registry..."
  podman push $REGISTRY/e-commerce-saga/$service-service:latest --tls-verify=false
done

echo "All images pushed to OpenShift registry successfully!" 
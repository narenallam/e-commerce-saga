#!/bin/bash

# Make script exit if any command fails
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}E-Commerce Saga - OpenShift Deployment${NC}"
echo -e "========================================\n"

# Check if OpenShift CLI is installed
if ! command -v oc &> /dev/null; then
    echo -e "${RED}Error: OpenShift CLI (oc) is not installed.${NC}"
    echo "Please install the OpenShift CLI first."
    exit 1
fi

# Check if Helm is installed
if ! command -v helm &> /dev/null; then
    echo -e "${RED}Error: Helm is not installed.${NC}"
    echo "Please install Helm first."
    exit 1
fi

# Check if OpenShift is running
echo -e "${YELLOW}Checking if OpenShift Local is running...${NC}"
if ! oc status &> /dev/null; then
    echo -e "${RED}Error: OpenShift is not running or you're not logged in.${NC}"
    echo "Please start OpenShift Local (CRC) and login with:"
    echo "  oc login -u developer -p developer"
    exit 1
fi

echo -e "${GREEN}✓ OpenShift is running and you're logged in.${NC}"

# Get the current logged-in user
CURRENT_USER=$(oc whoami)
echo -e "Current user: ${YELLOW}$CURRENT_USER${NC}"

# Building images with Podman
echo -e "\n${YELLOW}Step 1: Building container images with Podman${NC}"
echo -e "----------------------------------------"
chmod +x ./build-podman.sh
./build-podman.sh

# Clean up existing resources to free memory
echo -e "\n${YELLOW}Step 2: Cleaning up existing resources${NC}"
echo -e "----------------------------------------"
echo -e "This will help free up memory for the new deployment."

# Create project if it doesn't exist
if ! oc get project e-commerce-saga &> /dev/null; then
    echo "Creating project 'e-commerce-saga'..."
    oc new-project e-commerce-saga
else
    echo "Project 'e-commerce-saga' already exists."
    oc project e-commerce-saga
fi

# Clean up all existing resources from previous deployments
echo "Cleaning up all existing resources..."
oc delete all --selector=release=e-commerce-saga -n e-commerce-saga --ignore-not-found=true
oc delete pvc --selector=release=e-commerce-saga -n e-commerce-saga --ignore-not-found=true

# Delete previous standalone deployments if they exist
for service in order inventory payment shipping notification; do
    if oc get deployment $service-service -n e-commerce-saga &> /dev/null; then
        echo "Deleting existing $service-service deployment..."
        oc delete deployment $service-service -n e-commerce-saga
    fi
    
    if oc get service $service-service -n e-commerce-saga &> /dev/null; then
        echo "Deleting existing $service-service service..."
        oc delete service $service-service -n e-commerce-saga
    fi
    
    if oc get route $service-service -n e-commerce-saga &> /dev/null; then
        echo "Deleting existing $service-service route..."
        oc delete route $service-service -n e-commerce-saga
    fi
done

# Get registry route
REGISTRY="$(oc get route default-route -n openshift-image-registry --template='{{ .spec.host }}')"

# Deploy with Helm
echo -e "\n${YELLOW}Step 3: Deploying with Helm${NC}"
echo -e "----------------------------------------"
echo -e "Installing the application with Helm..."

# Use --set to specify minimal resource requirements for memory-constrained environments
helm upgrade --install e-commerce-saga ./helm \
  --namespace e-commerce-saga \
  --create-namespace \
  --set global.imageRegistry=$REGISTRY/e-commerce-saga \
  --set global.environment=production \
  --set global.resources.requests.memory=64Mi \
  --set global.resources.limits.memory=128Mi \
  --set mongodb.persistence.enabled=false \
  --set mongodb.resources.requests.memory=128Mi \
  --set mongodb.resources.limits.memory=256Mi

# Wait for deployments to be ready with longer timeout
echo -e "\n${YELLOW}Step 4: Waiting for deployments to be ready${NC}"
echo -e "----------------------------------------"
echo "This may take a few minutes..."

# Wait for pods to start (with || true to continue even if they're not ready yet)
echo "Waiting for pods to start (will continue after 20 seconds regardless)..."
sleep 20

# Get service routes
echo -e "\n${YELLOW}Step 5: Getting service routes${NC}"
echo -e "----------------------------------------"
echo "Here are the routes to access your services:"

ORDER_ROUTE=$(oc get route e-commerce-saga-order-service -n e-commerce-saga -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not available yet")
INVENTORY_ROUTE=$(oc get route e-commerce-saga-inventory-service -n e-commerce-saga -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not available yet")
PAYMENT_ROUTE=$(oc get route e-commerce-saga-payment-service -n e-commerce-saga -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not available yet")
SHIPPING_ROUTE=$(oc get route e-commerce-saga-shipping-service -n e-commerce-saga -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not available yet")
NOTIFICATION_ROUTE=$(oc get route e-commerce-saga-notification-service -n e-commerce-saga -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not available yet")

echo -e "Order Service:       ${GREEN}https://$ORDER_ROUTE${NC}"
echo -e "Inventory Service:   ${GREEN}https://$INVENTORY_ROUTE${NC}"
echo -e "Payment Service:     ${GREEN}https://$PAYMENT_ROUTE${NC}"
echo -e "Shipping Service:    ${GREEN}https://$SHIPPING_ROUTE${NC}"
echo -e "Notification Service:${GREEN}https://$NOTIFICATION_ROUTE${NC}"

echo -e "\n${YELLOW}Pod Status:${NC}"
oc get pods -n e-commerce-saga

echo -e "\n${GREEN}Deployment completed!${NC}"
echo -e "To access the OpenShift console, visit: https://console-openshift-console.apps-crc.testing"
echo -e "API documentation is available at: https://$ORDER_ROUTE/docs" 
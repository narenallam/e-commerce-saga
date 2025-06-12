#!/bin/bash

echo "📊 Installing Kubernetes Metrics Server..."
echo "==========================================="

# Check if metrics server is already installed
if kubectl get deployment metrics-server -n kube-system >/dev/null 2>&1; then
    echo "✅ Metrics server is already installed"
    exit 0
fi

echo "📦 Applying metrics server configuration..."

# Apply metrics server with insecure TLS (for local development)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

echo "⏳ Waiting for metrics server to be ready..."
sleep 5

# Patch metrics server for local development (insecure TLS)
kubectl patch deployment metrics-server -n kube-system --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'

echo "⏳ Waiting for metrics server to restart..."
kubectl rollout status deployment/metrics-server -n kube-system --timeout=120s

echo "✅ Metrics server installation complete!"
echo "💡 You can now use 'kubectl top nodes' and 'kubectl top pods'"
echo "💡 The 'make monitor' command will show resource usage" 
# Makefile for E-commerce Saga System (Kubernetes Only)

.PHONY: help install test build deploy clean logs port-forward dev-reset cluster-info monitor metrics

help:
	@source scripts/console-ui.sh && \
	clear && \
	print_header "🚀 E-COMMERCE SAGA SYSTEM - KUBERNETES DEPLOYMENT" && \
	printf "\033[0;36m🎯 Beautiful Console Interface for Kubernetes Management\033[0m\n" && \
	printf "\n" && \
	printf "\033[1;37m\033[4m🏗️ CORE COMMANDS\033[0m\n" && \
	printf "\033[0;32m  🔨 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "build" "Build Docker images for Kubernetes deployment" && \
	printf "\033[0;32m  🚀 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "deploy" "Deploy to Kubernetes cluster (production-ready)" && \
	printf "\033[0;32m  🧹 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "clean" "Clean up all Kubernetes resources" && \
	printf "\033[0;32m  🔄 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "dev-reset" "Complete development environment reset" && \
	printf "\n" && \
	printf "\033[1;37m\033[4m🎛️ MONITORING & OPERATIONS\033[0m\n" && \
	printf "\033[0;35m  📋 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "logs" "Show real-time pod logs" && \
	printf "\033[0;35m  📦 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "pods" "Show current pod status" && \
	printf "\033[0;35m  🩺 %-15s\033[0m \033[1;37m%-50s\033[0m \033[0;33m[✨ ENHANCED]\033[0m\n" "health" "Service health & application status monitoring" && \
	printf "\033[0;35m  🌐 %-15s\033[0m \033[1;37m%-50s\033[0m \033[0;33m[✨ ENHANCED]\033[0m\n" "cluster-info" "Cluster infrastructure & topology details" && \
	printf "\033[0;35m  📊 %-15s\033[0m \033[1;37m%-50s\033[0m \033[0;33m[✨ ENHANCED]\033[0m\n" "monitor" "Real-time cluster monitoring dashboard" && \
	printf "\033[0;35m  📈 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "metrics" "Install metrics server for resource monitoring" && \
	printf "\n" && \
	printf "\033[1;37m\033[4m🔗 CONNECTIVITY\033[0m\n" && \
	printf "\033[0;36m  🌍 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "port-forward" "Setup local access to all services" && \
	printf "\n" && \
	printf "\033[1;37m\033[4m💾 DATA MANAGEMENT\033[0m\n" && \
	printf "\033[0;33m  📊 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "generate-data" "Generate comprehensive test data (needs port-forward)" && \
	printf "\n" && \
	printf "\033[1;37m💡 QUICK START WORKFLOW:\033[0m\n" && \
	printf "\033[0;36m   1. make build\033[0m       \033[0;37m# Build all images\033[0m\n" && \
	printf "\033[0;36m   2. make deploy\033[0m      \033[0;37m# Deploy to cluster\033[0m\n" && \
	printf "\033[0;36m   3. make health\033[0m      \033[0;37m# Check service health\033[0m\n" && \
	printf "\033[0;36m   4. make port-forward\033[0m \033[0;37m# Enable local access\033[0m\n" && \
	printf "\033[0;36m   5. make monitor\033[0m     \033[0;37m# Real-time monitoring\033[0m\n" && \
	printf "\n" && \
	printf "\033[1;33m🎨 BEAUTIFUL FEATURES:\033[0m\n" && \
	printf "\033[0;32m   ✨ Color-coded status indicators\033[0m\n" && \
	printf "\033[0;32m   📊 Visual progress bars and charts\033[0m\n" && \
	printf "\033[0;32m   🏠 Master/Worker node identification\033[0m\n" && \
	printf "\033[0;32m   📦 Pod placement visualization\033[0m\n" && \
	printf "\033[0;32m   🔄 Real-time status monitoring\033[0m\n"

install:
	@echo "📦 Installing dependencies..."
	python3 -m pip install -r config/requirements.txt --break-system-packages --user
	python3 -m pip install faker pytest pytest-asyncio --break-system-packages --user

test:
	@echo "🧪 Running tests..."
	PYTHONPATH=src pytest tests/ -v

build:
	@echo "🏗️ Building Docker images for Kubernetes..."
	docker build -f deployments/kubernetes/Dockerfile -t e-commerce-saga/order-service:latest --build-arg SERVICE_DIR=order .
	docker build -f deployments/kubernetes/Dockerfile -t e-commerce-saga/inventory-service:latest --build-arg SERVICE_DIR=inventory .
	docker build -f deployments/kubernetes/Dockerfile -t e-commerce-saga/payment-service:latest --build-arg SERVICE_DIR=payment .
	docker build -f deployments/kubernetes/Dockerfile -t e-commerce-saga/shipping-service:latest --build-arg SERVICE_DIR=shipping .
	docker build -f deployments/kubernetes/Dockerfile -t e-commerce-saga/notification-service:latest --build-arg SERVICE_DIR=notification .
	docker build -f deployments/kubernetes/Dockerfile -t e-commerce-saga/saga-coordinator:latest --build-arg SERVICE_DIR=coordinator .

deploy:
	@echo "🚀 Deploying to Kubernetes..."
	kubectl apply -f deployments/kubernetes/k8s-production-deployment.yaml
	@echo "⏳ Waiting for deployment to be ready..."
	kubectl wait --for=condition=available --timeout=300s deployment --all -n e-commerce-saga

logs:
	@echo "📋 Showing pod logs..."
	kubectl logs -f -l app=saga-coordinator -n e-commerce-saga --tail=50

pods:
	@echo "📋 Showing pod status..."
	kubectl get pods -n e-commerce-saga -o wide

health:
	@PYTHONPATH=src python3 ./scripts/health-monitor-rich.py

cluster-info:
	@PYTHONPATH=src python3 ./scripts/cluster-info-rich.py

monitor:
	@PYTHONPATH=src python3 ./scripts/monitor-rich.py

metrics:
	@echo "📊 Installing Kubernetes Metrics Server..."
	@./scripts/install-metrics-server.sh

port-forward:
	@echo "📡 Setting up port forwarding..."
	@echo "💡 Services will be accessible at localhost:800X and localhost:9000"
	@pkill -f "kubectl port-forward.*e-commerce-saga" || true
	kubectl port-forward -n e-commerce-saga svc/order-service 8000:8000 &
	kubectl port-forward -n e-commerce-saga svc/inventory-service 8001:8001 &
	kubectl port-forward -n e-commerce-saga svc/payment-service 8002:8002 &
	kubectl port-forward -n e-commerce-saga svc/shipping-service 8003:8003 &
	kubectl port-forward -n e-commerce-saga svc/notification-service 8004:8004 &
	kubectl port-forward -n e-commerce-saga svc/saga-coordinator 9000:9000 &
	kubectl port-forward -n e-commerce-saga svc/mongodb 27017:27017 &
	@sleep 3
	@echo "✅ Port forwarding setup complete"
	@echo "🔗 Access services:"
	@echo "   Saga Coordinator: http://localhost:9000/docs"
	@echo "   Order Service: http://localhost:8000/docs"
	@echo "   MongoDB: mongodb://localhost:27017"

generate-data:
	@echo "📊 Generating test data..."
	@echo "💡 Requires port-forward to be active"
	PYTHONPATH=src python3 tools/test_data_generator.py --reset

clean:
	@echo "🧹 Cleaning up Kubernetes resources..."
	@pkill -f "kubectl port-forward.*e-commerce-saga" || true
	kubectl delete namespace e-commerce-saga --ignore-not-found
	kubectl delete priorityclass high-priority medium-priority low-priority --ignore-not-found
	@echo "✅ Kubernetes cleanup completed"

dev-reset: clean build deploy
	@echo "🔄 Development environment reset complete"
	@echo "💡 Run 'make port-forward' to access services locally"
	@echo "💡 Run 'make generate-data' to populate test data"

status:
	@echo "📊 Kubernetes Cluster Status"
	@echo "Pods:"
	kubectl get pods -n e-commerce-saga 2>/dev/null || echo "  No pods found (run 'make deploy')"
	@echo ""
	@echo "Services:"
	kubectl get svc -n e-commerce-saga 2>/dev/null || echo "  No services found"
	@echo ""
	@echo "💡 Quick commands:"
	@echo "  make deploy      - Deploy the system"
	@echo "  make port-forward - Access services locally"
	@echo "  make health      - Check service health" 
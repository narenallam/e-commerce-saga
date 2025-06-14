# Makefile for E-commerce Saga System (Kubernetes Only)

.PHONY: help install test build deploy clean logs port-forward dev-reset cluster-info monitor metrics test-monitor

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
	printf "\033[0;35m  📊 %-15s\033[0m \033[1;37m%-50s\033[0m \033[0;33m[📋 SNAPSHOT]\033[0m\n" "monitor" "One-time cluster monitoring snapshot report" && \
	printf "\033[0;35m  📸 %-15s\033[0m \033[1;37m%-50s\033[0m \033[0;33m[📋 SNAPSHOT]\033[0m\n" "test-monitor" "Snapshot view of complete monitoring layout" && \
	printf "\033[0;35m  📈 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "metrics" "Install metrics server for resource monitoring" && \
	printf "\n" && \
	printf "\033[1;37m\033[4m🔗 CONNECTIVITY\033[0m\n" && \
	printf "\033[0;36m  🌍 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "port-forward" "Setup local access to all services" && \
	printf "\n" && \
	printf "\033[1;37m\033[4m💾 DATA MANAGEMENT\033[0m\n" && \
	printf "\033[0;33m  📊 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "generate-data" "Generate comprehensive test data (needs port-forward)" && \
	printf "\033[0;33m  🔧 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "generate-test-data" "Generate test data for validation scenarios" && \
	printf "\n" && \
	printf "\033[1;37m\033[4m🧪 TESTING & VALIDATION\033[0m\n" && \
	printf "\033[0;31m  📊 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "test-coverage" "Run comprehensive test coverage analysis" && \
	printf "\033[0;31m  📄 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "test-report" "Generate detailed test coverage report" && \
	printf "\033[0;31m  🔍 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "validate-system" "Run full system validation with reports" && \
	printf "\033[0;31m  🧪 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "quick-test" "Run quick system validation tests" && \
	printf "\033[0;31m  🔍 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "functional-test" "Run comprehensive functional test scenarios" && \
	printf "\033[0;31m  🏢 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "business-flows" "Run business workflow functional tests" && \
	printf "\033[0;31m  ⚡ %-15s\033[0m \033[1;37m%-50s\033[0m\n" "performance-test" "Run performance and load functional tests" && \
	printf "\033[0;31m  🚀 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "load-test" "Run basic load test (10 users, 3 minutes)" && \
	printf "\033[0;31m  🧪 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "load-test-scenarios" "Run predefined load test scenarios" && \
	printf "\033[0;31m  💪 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "stress-test" "Run stress test (50 users, 10 minutes)" && \
	printf "\033[0;31m  💥 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "chaos-test" "Run comprehensive chaos engineering test" && \
	printf "\033[0;31m  💥 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "chaos-pod" "Run pod restart chaos test (quick)" && \
	printf "\033[0;31m  ✅ %-15s\033[0m \033[1;37m%-50s\033[0m\n" "validate-system" "Run system validation suite" && \
	printf "\033[0;31m  🎯 %-15s\033[0m \033[1;37m%-50s\033[0m\n" "test-all" "Run complete test suite (all tests)" && \
	printf "\n" && \
	printf "\033[1;37m💡 QUICK START WORKFLOW:\033[0m\n" && \
	printf "\033[0;36m   1. make build\033[0m       \033[0;37m# Build all images\033[0m\n" && \
	printf "\033[0;36m   2. make deploy\033[0m      \033[0;37m# Deploy to cluster\033[0m\n" && \
	printf "\033[0;36m   3. make health\033[0m      \033[0;37m# Check service health\033[0m\n" && \
	printf "\033[0;36m   4. make port-forward\033[0m \033[0;37m# Enable local access\033[0m\n" && \
	printf "\033[0;36m   5. make monitor\033[0m     \033[0;37m# Snapshot monitoring\033[0m\n" && \
	printf "\n" && \
	printf "\033[1;33m🎨 BEAUTIFUL FEATURES:\033[0m\n" && \
	printf "\033[0;32m   ✨ Color-coded status indicators\033[0m\n" && \
	printf "\033[0;32m   📊 Visual progress bars and charts\033[0m\n" && \
	printf "\033[0;32m   🏠 Master/Worker node identification\033[0m\n" && \
	printf "\033[0;32m   📦 Pod placement visualization\033[0m\n" && \
	printf "\033[0;32m   🔄 Comprehensive status reporting\033[0m\n"

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
	kubectl apply -f deployments/kubernetes/k8s-local-deployment.yaml
	@echo "⏳ Waiting for deployment to be ready..."
	kubectl wait --for=condition=available --timeout=300s deployment --all -n e-commerce-saga

logs:
	@echo "📋 Showing pod logs..."
	kubectl logs -f -l app=saga-coordinator -n e-commerce-saga --tail=50

pods:
	@echo "📋 Showing pod status..."
	kubectl get pods -n e-commerce-saga -o wide

health:
	@echo "🩺 Starting comprehensive health check..."
	@echo "📡 Setting up port forwarding for health checks..."
	@pkill -f "kubectl port-forward.*e-commerce-saga" || true
	@sleep 2
	@kubectl port-forward -n e-commerce-saga svc/order-service 8000:8000 > /dev/null 2>&1 &
	@kubectl port-forward -n e-commerce-saga svc/inventory-service 8001:8001 > /dev/null 2>&1 &
	@kubectl port-forward -n e-commerce-saga svc/payment-service 8002:8002 > /dev/null 2>&1 &
	@kubectl port-forward -n e-commerce-saga svc/shipping-service 8003:8003 > /dev/null 2>&1 &
	@kubectl port-forward -n e-commerce-saga svc/notification-service 8004:8004 > /dev/null 2>&1 &
	@kubectl port-forward -n e-commerce-saga svc/saga-coordinator 9000:9000 > /dev/null 2>&1 &
	@kubectl port-forward -n e-commerce-saga svc/redis 6379:6379 > /dev/null 2>&1 &
	@echo "⏳ Waiting for port forwards to stabilize..."
	@sleep 6
	@PYTHONPATH=src python3 ./scripts/health-monitor-rich.py

cluster-info:
	@PYTHONPATH=src python3 ./scripts/cluster-info-rich.py

monitor:
	@echo "📊 Generating cluster monitoring snapshot..."
	@PYTHONPATH=src python3 ./scripts/monitor-snapshot.py

test-monitor:
	@PYTHONPATH=src python3 ./scripts/monitor-snapshot.py

metrics:
	@echo "📊 Installing Kubernetes Metrics Server..."
	@./scripts/install-metrics-server.sh

port-forward:
	@echo "📡 Setting up port forwarding..."
	@echo "💡 Services will be accessible at localhost:800X, Redis:6379, MongoDB:27017, and Saga:9000"
	@pkill -f "kubectl port-forward.*e-commerce-saga" || true
	kubectl port-forward -n e-commerce-saga svc/order-service 8000:8000 &
	kubectl port-forward -n e-commerce-saga svc/inventory-service 8001:8001 &
	kubectl port-forward -n e-commerce-saga svc/payment-service 8002:8002 &
	kubectl port-forward -n e-commerce-saga svc/shipping-service 8003:8003 &
	kubectl port-forward -n e-commerce-saga svc/notification-service 8004:8004 &
	kubectl port-forward -n e-commerce-saga svc/saga-coordinator 9000:9000 &
	kubectl port-forward -n e-commerce-saga svc/redis 6379:6379 &
	kubectl port-forward -n e-commerce-saga svc/mongodb 27017:27017 &
	@sleep 3
	@echo "✅ Port forwarding setup complete"
	@echo "🔗 Access services:"
	@echo "   Saga Coordinator: http://localhost:9000/docs"
	@echo "   Order Service: http://localhost:8000/docs"
	@echo "   Redis: redis://localhost:6379"
	@echo "   MongoDB: mongodb://localhost:27017"

generate-data:
	@echo "📊 Generating test data..."
	@echo "💡 Requires port-forward to be active"
	PYTHONPATH=src python3 tools/test_data_generator.py --reset

# Testing & Validation Commands
generate-test-data:
	@echo "🔧 Generating comprehensive test data..."
	@chmod +x scripts/test-data-generator.py
	@PYTHONPATH=src python3 scripts/test-data-generator.py --customers 1000 --products 500 --orders 5000

# Test Coverage & Reporting
test-coverage:
	@echo "📊 Running comprehensive test coverage analysis..."
	@chmod +x test-coverage.py
	@python test-coverage.py

test-report:
	@echo "📄 Generating test coverage report..."
	@python test-coverage.py

load-test:
	@echo "🚀 Running basic load test..."
	@chmod +x scripts/load-test.py
	@PYTHONPATH=src python3 scripts/load-test.py --users 10 --duration 3

load-test-scenarios:
	@echo "🧪 Running predefined load test scenarios..."
	@chmod +x scripts/load-test.py
	@PYTHONPATH=src python3 scripts/load-test.py --scenarios

stress-test:
	@echo "💪 Running stress test..."
	@chmod +x scripts/load-test.py
	@PYTHONPATH=src python3 scripts/load-test.py --users 50 --rate 5 --duration 10

chaos-test:
	@echo "💥 Running comprehensive chaos engineering test..."
	@chmod +x scripts/chaos-test.py
	@PYTHONPATH=src python3 scripts/chaos-test.py --duration 10

chaos-pod:
	@echo "💥 Running pod restart chaos test..."
	@chmod +x scripts/chaos-test.py
	@PYTHONPATH=src python3 scripts/chaos-test.py --type pod_restart --service order-service --duration 5

# Quick Testing
quick-test:
	@echo "🧪 Running quick functional tests..."
	@chmod +x quick-test.py
	@python quick-test.py

functional-test:
	@echo "🔍 Running comprehensive functional tests..."
	@chmod +x tests/integration/functional-test-comprehensive.py
	@PYTHONPATH=src python3 tests/integration/functional-test-comprehensive.py

business-flows:
	@echo "🏢 Running business workflow functional tests..."
	@chmod +x tests/integration/business-flow-tests.py
	@PYTHONPATH=src python3 tests/integration/business-flow-tests.py

performance-test:
	@echo "⚡ Running performance functional tests..."
	@chmod +x tests/integration/performance-tests.py
	@PYTHONPATH=src python3 tests/integration/performance-tests.py

validate-system:
	@echo "✅ Running comprehensive system validation..."
	@make health
	@make functional-test
	@make business-flows
	@make test-coverage

test-all:
	@echo "🎯 Running complete test suite..."
	@make health
	@make generate-test-data
	@make functional-test
	@make business-flows
	@make performance-test
	@make load-test
	@make chaos-pod
	@echo "🏆 Complete test suite finished!"

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
# Makefile for E-commerce Saga System

.PHONY: help install test build deploy clean logs monitor logs-stats logs-compress logs-cleanup

# Default target
help:
	@echo "🚀 E-commerce Saga System - Available Commands"
	@echo ""
	@echo "Development:"
	@echo "  install     Install dependencies"
	@echo "  test        Run all tests"
	@echo "  test-unit   Run unit tests"
	@echo "  test-func   Run functional tests"
	@echo "  test-chaos  Run chaos tests"
	@echo "  test-perf   Run performance tests"
	@echo ""
	@echo "Data Management:"
	@echo "  generate-data    Generate test data"
	@echo "  check-consistency Check data consistency"
	@echo "  cleanup-data     Clean up test data"
	@echo ""
	@echo "Deployment:"
	@echo "  build       Build Docker images"
	@echo "  deploy-k8s  Deploy to Kubernetes"
	@echo "  deploy-compose Deploy with Docker Compose"
	@echo ""
	@echo "Monitoring:"
	@echo "  logs        Show service logs"
	@echo "  monitor     Start monitoring dashboard"
	@echo "  health      Check service health"
	@echo "  analyze     Analyze system logs"
	@echo ""
	@echo "Log Management:"
	@echo "  logs-stats     Show log statistics"
	@echo "  logs-compress  Compress old log files"
	@echo "  logs-cleanup   Clean up old compressed logs"
	@echo "  logs-rotate    Rotate logs for specific service"
	@echo ""
	@echo "Utilities:"
	@echo "  setup       Setup development environment"
	@echo "  port-forward Setup Kubernetes port forwarding"
	@echo "  clean       Clean up resources"

# Development commands
install:
	@echo "📦 Installing dependencies..."
	python3 -m pip install -r config/requirements.txt --break-system-packages --user
	python3 -m pip install faker pytest pytest-asyncio --break-system-packages --user
	@echo "Installing k6 load testing tool..."
	@which k6 >/dev/null 2>&1 || (echo "Please install k6 manually: https://k6.io/docs/get-started/installation/" && echo "On macOS: brew install k6" && echo "On Ubuntu: sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69 && echo 'deb https://dl.k6.io/deb stable main' | sudo tee /etc/apt/sources.list.d/k6.list && sudo apt-get update && sudo apt-get install k6")

test: test-unit test-func test-chaos
	@echo "✅ All tests completed"

test-unit:
	@echo "🧪 Running unit tests..."
	PYTHONPATH=src pytest tests/ -v

test-func:
	@echo "🔧 Running functional tests..."
	PYTHONPATH=src python3 scripts/test/functional_tests.py

test-chaos:
	@echo "🔥 Running chaos tests..."
	PYTHONPATH=src python3 scripts/test/chaos_testing.py

test-perf:
	@echo "⚡ Running performance tests..."
	bash scripts/test/performance_test.sh

# Data management
generate-data:
	@echo "📊 Generating test data..."
	PYTHONPATH=src python3 tools/test_data_generator.py --reset

check-consistency:
	@echo "🔍 Checking data consistency..."
	PYTHONPATH=src python3 tools/data_consistency_checker.py

cleanup-data:
	@echo "🧹 Cleaning up test data..."
	PYTHONPATH=src python3 tools/test_data_generator.py --cleanup

# Docker build
build:
	@echo "🏗️ Building Docker images..."
	docker build -f deployments/docker/Dockerfile -t e-commerce-saga/order-service:latest --build-arg SERVICE_DIR=order .
	docker build -f deployments/docker/Dockerfile -t e-commerce-saga/inventory-service:latest --build-arg SERVICE_DIR=inventory .
	docker build -f deployments/docker/Dockerfile -t e-commerce-saga/payment-service:latest --build-arg SERVICE_DIR=payment .
	docker build -f deployments/docker/Dockerfile -t e-commerce-saga/shipping-service:latest --build-arg SERVICE_DIR=shipping .
	docker build -f deployments/docker/Dockerfile -t e-commerce-saga/notification-service:latest --build-arg SERVICE_DIR=notification .
	docker build -f deployments/docker/Dockerfile -t e-commerce-saga/saga-coordinator:latest --build-arg SERVICE_DIR=coordinator .

# Deployment
deploy-k8s:
	@echo "🚀 Deploying to Kubernetes..."
	kubectl apply -f deployments/kubernetes/k8s-local-deployment.yaml
	@echo "⏳ Waiting for deployment to be ready..."
	kubectl wait --for=condition=available --timeout=300s deployment --all -n e-commerce-saga

deploy-compose:
	@echo "🐳 Deploying with Docker Compose..."
	docker-compose -f deployments/docker/docker-compose.yml up -d --build
	@echo "⏳ Waiting for services to be ready..."
	sleep 30

# Monitoring and logs
logs:
	@echo "📋 Showing service logs..."
	kubectl logs -f -l app=order-service -n e-commerce-saga --tail=100

monitor:
	@echo "🖥️ Starting monitoring dashboard..."
	PYTHONPATH=src python3 scripts/monitoring/monitoring_dashboard.py

health:
	@echo "🩺 Checking service health..."
	PYTHONPATH=src python3 scripts/monitoring/check_health.py

analyze:
	@echo "📊 Analyzing system logs..."
	PYTHONPATH=src python3 scripts/monitoring/log_analyzer.py --report health

# Log management
logs-stats:
	@echo "📊 Showing log statistics..."
	PYTHONPATH=src python3 scripts/monitoring/log_rotation_manager.py --stats

logs-compress:
	@echo "🗜️ Compressing old log files..."
	PYTHONPATH=src python3 scripts/monitoring/log_rotation_manager.py --compress 7

logs-cleanup:
	@echo "🧹 Cleaning up old compressed logs..."
	PYTHONPATH=src python3 scripts/monitoring/log_rotation_manager.py --cleanup 30

logs-rotate:
	@echo "🔄 Rotating logs..."
	@read -p "Enter service name: " service; \
	PYTHONPATH=src python3 scripts/monitoring/log_rotation_manager.py --rotate $$service

# Setup and utilities
setup:
	@echo "🔧 Setting up development environment..."
	bash tools/setup_test_environment.sh

port-forward:
	@echo "📡 Setting up port forwarding..."
	kubectl port-forward -n e-commerce-saga svc/order-service 8000:8000 &
	kubectl port-forward -n e-commerce-saga svc/inventory-service 8001:8001 &
	kubectl port-forward -n e-commerce-saga svc/payment-service 8002:8002 &
	kubectl port-forward -n e-commerce-saga svc/shipping-service 8003:8003 &
	kubectl port-forward -n e-commerce-saga svc/notification-service 8004:8004 &
	kubectl port-forward -n e-commerce-saga svc/saga-coordinator 9000:9000 &
	kubectl port-forward -n e-commerce-saga svc/mongodb 27017:27017 &
	@echo "✅ Port forwarding setup complete"

clean:
	@echo "🧹 Cleaning up resources..."
	docker-compose -f deployments/docker/docker-compose.yml down -v || true
	kubectl delete namespace e-commerce-saga --ignore-not-found
	docker system prune -f

# Database operations
db-backup:
	@echo "💾 Backing up database..."
	mongodump --uri="mongodb://localhost:27017/ecommerce_saga" --out=backups/$(shell date +%Y%m%d_%H%M%S)

db-restore:
	@echo "♻️ Restoring database..."
	@read -p "Enter backup directory: " backup_dir; \
	mongorestore --uri="mongodb://localhost:27017" $$backup_dir

# Development helpers
dev-setup: install generate-data
	@echo "🏗️ Development environment setup complete"

dev-reset: clean deploy-compose generate-data
	@echo "🔄 Development environment reset complete"

# CI/CD helpers
ci-test: test check-consistency
	@echo "✅ CI tests completed"

ci-build: build
	@echo "🏗️ CI build completed"

# Documentation
docs:
	@echo "📚 Opening documentation..."
	@echo "Main Documentation: README.md"
	@echo "API Documentation: http://localhost:8000/docs"
	@echo "Monitoring Dashboard: make monitor"

# Security scanning (placeholder)
security-scan:
	@echo "🔒 Running security scan..."
	# Add security scanning tools like bandit, safety, etc.
	@echo "⚠️ Security scanning not implemented yet"

# Version and release management
version:
	@echo "📌 Current version: $(shell grep version pyproject.toml | cut -d'"' -f2 2>/dev/null || echo "Not available")"

tag-release:
	@read -p "Enter version tag: " tag; \
	git tag -a $$tag -m "Release $$tag"; \
	git push origin $$tag; \
	echo "🏷️ Tagged release $$tag" 
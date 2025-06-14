# E-Commerce Saga System Testing Guide

## Overview
This document outlines comprehensive testing scenarios for validating both functional and technical aspects of our Kubernetes-based e-commerce saga system with 6 microservices.

## System Architecture
- **Order Service** (3 replicas) - Port 8000
- **Inventory Service** (2 replicas) - Port 8001  
- **Payment Service** (3 replicas) - Port 8002
- **Shipping Service** (2 replicas) - Port 8003
- **Notification Service** (1 replica) - Port 8004
- **Saga Coordinator** (2 replicas) - Port 9000
- **MongoDB** (1 replica) - Port 27017
- **Redis** (1 replica) - Port 6379
- **Kafka** (2 replicas) - Port 9092
- **Zookeeper** (1 replica) - Port 2181

## Test Categories

### 1. UNIT TESTING

#### 1.1 Service Unit Tests

##### Order Service Tests (`test_order_service.py`)
- Order creation success and failure scenarios
- Order retrieval and not found cases
- Order status updates
- Order cancellation
- Database operation validation
- Input validation and error handling

##### Saga Coordinator Tests (`test_saga_coordinator.py`)
- Saga initialization and step definition
- Successful saga execution through all steps
- Failure and compensation scenarios
- Step context preparation and updates
- Service health checks
- Compensation context preparation
- Saga status message handling

##### Inventory Service Tests (`test_inventory_service.py`)
- Inventory reservation
- Stock updates
- Product availability checks
- Reservation release
- Concurrent inventory operations

##### Payment Service Tests (`test_payment_service.py`)
- Payment processing
- Transaction validation
- Refund handling
- Payment status updates
- Error scenarios

##### Shipping Service Tests (`test_shipping_service.py`)
- Shipping schedule creation
- Tracking updates
- Delivery status management
- Address validation
- Shipping method selection

##### Notification Service Tests (`test_notification_service.py`)
- Notification creation
- Message delivery
- Template handling
- Notification status tracking
- Error handling

#### 1.2 Integration Tests

##### Kafka Integration Tests (`test_kafka_integration.py`)
- Event publishing
- Event consumption
- Message ordering
- Error handling
- Retry mechanisms
- Dead letter queue handling

##### Redis Caching Tests (`test_redis_caching.py`)
- Cache operations
- Cache invalidation
- Cache consistency
- Performance metrics
- Error handling

### 2. FUNCTIONAL TESTING

#### 2.1 Happy Path Scenarios

##### Test Case F1.1: Complete Order Success Flow
**Objective**: Validate end-to-end order processing with all services succeeding
**Test Data**:
```json
{
  "customer_id": "test-customer-123",
  "items": [
    {
      "product_id": "prod-1",
      "name": "Test Product",
      "quantity": 2,
      "unit_price": 99.99,
      "total_price": 199.98
    }
  ],
  "total_amount": 199.98,
  "shipping_address": {
    "street": "123 Test St",
    "city": "Test City",
    "state": "TS",
    "zip_code": "12345",
    "country": "US"
  },
  "payment_method": "CREDIT_CARD",
  "shipping_method": "STANDARD"
}
```

#### 2.2 Saga Compensation Scenarios

##### Test Case F2.1: Payment Failure Compensation
**Objective**: Validate rollback when payment fails
**Test Steps**:
1. Create order with valid inventory
2. Simulate payment service failure
3. Verify inventory reservation is released
4. Confirm order status is "FAILED"

##### Test Case F2.2: Inventory Failure Compensation
**Objective**: Test saga compensation when inventory check fails
**Test Steps**:
1. Create order with insufficient inventory
2. Verify order cancellation
3. Confirm proper error handling

### 3. TECHNICAL TESTING

#### 3.1 Performance Testing

##### Test Case T1.1: Service Response Times
**Objective**: Validate service performance under load
**Metrics**:
- Response time < 500ms for 95% of requests
- Error rate < 1%
- Throughput > 100 requests/second

##### Test Case T1.2: Saga Execution Performance
**Objective**: Measure end-to-end saga execution time
**Metrics**:
- Complete saga execution < 2 seconds
- Compensation execution < 1 second
- Event processing latency < 100ms

#### 3.2 Resilience Testing

##### Test Case T2.1: Service Failure Handling
**Objective**: Test system behavior during service failures
**Scenarios**:
- Service pod termination
- Network partition
- Database connection loss
- Kafka broker failure

##### Test Case T2.2: Recovery Testing
**Objective**: Verify system recovery after failures
**Scenarios**:
- Service restart
- Database failover
- Kafka partition recovery
- Redis failover

### 4. TEST DATA GENERATION

#### 4.1 Test Data Templates
```json
{
  "order_template": {
    "customer_id": "test-customer-{id}",
    "items": [
      {
        "product_id": "prod-{id}",
        "name": "Test Product {id}",
        "quantity": 1,
        "unit_price": 99.99,
        "total_price": 99.99
      }
    ],
    "total_amount": 99.99,
    "shipping_address": {
      "street": "123 Test St",
      "city": "Test City",
      "state": "TS",
      "zip_code": "12345",
      "country": "US"
    }
  }
}
```

### 5. TEST EXECUTION

#### 5.1 Running Tests
```bash
# Run all tests
pytest tests/

# Run specific service tests
pytest tests/test_order_service.py
pytest tests/test_saga_coordinator.py

# Run with coverage
pytest --cov=src tests/

# Run performance tests
pytest tests/integration/test_performance.py
```

#### 5.2 Test Environment Setup
```bash
# Start test environment
make test-env-up

# Stop test environment
make test-env-down

# Reset test data
make test-data-reset
```

### 6. MONITORING AND METRICS

#### 6.1 Key Metrics
- Test coverage percentage
- Test execution time
- Success/failure rates
- Performance metrics
- Error rates

#### 6.2 Monitoring Tools
- Prometheus for metrics
- Grafana for visualization
- ELK stack for logs
- Jaeger for tracing

### 7. CONTINUOUS TESTING

#### 7.1 CI/CD Integration
- Automated test execution on pull requests
- Daily regression test runs
- Weekly performance test runs
- Monthly security scans

#### 7.2 Test Reports
- Test execution summary
- Coverage reports
- Performance metrics
- Error analysis

### 8. EMERGENCY PROCEDURES

#### 8.1 Test Failures
1. Stop test execution
2. Collect failure logs
3. Analyze root cause
4. Document findings
5. Implement fixes
6. Verify resolution

#### 8.2 Contact Information
- DevOps Team: devops@company.com
- Platform Team: platform@company.com
- Security Team: security@company.com

## Observability: Prometheus & Grafana

### Metrics Exposure
- All services expose a `/metrics` endpoint (Prometheus format)
- Metrics include: HTTP request count, latency, error rates, saga step durations, Kafka event counts

### Prometheus Setup
- Deployed in Kubernetes (see deployments/kubernetes/)
- Scrapes all service `/metrics` endpoints
- Example scrape config:
  ```yaml
  scrape_configs:
    - job_name: 'ecommerce-services'
      kubernetes_sd_configs:
        - role: endpoints
      relabel_configs:
        - source_labels: [__meta_kubernetes_service_label_app]
          regex: (order|inventory|payment|shipping|notification|saga-coordinator)-service
          action: keep
        - source_labels: [__meta_kubernetes_service_port_name]
          regex: metrics
          action: keep
  ```

### Grafana Dashboards
- Grafana deployed in Kubernetes (see deployments/kubernetes/)
- Connects to Prometheus as data source
- Dashboards:
  - HTTP request rates/latency/errors per service
  - Saga orchestration step durations and failures
  - Kafka event throughput and lag
  - Redis cache hit/miss rates
  - System health and resource usage

### Verification Steps
- Access Prometheus: `kubectl port-forward svc/prometheus 9090:9090 -n monitoring`
- Access Grafana: `kubectl port-forward svc/grafana 3000:3000 -n monitoring`
- Verify `/metrics` endpoint: `curl http://localhost:8000/metrics`
- Check dashboards for live metrics and alerts

---

*Last Updated: 2025-06-14*
*Version: 2.0*
*Status: Active* 
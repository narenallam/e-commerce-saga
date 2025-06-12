#!/bin/bash
# Performance Testing Script for E-commerce Saga System

set -e

echo "🚀 Starting Performance Test Suite..."

# Configuration
CONCURRENT_USERS=${1:-10}
TEST_DURATION=${2:-60}
ORDER_ENDPOINT="http://localhost:9000/api/coordinator/orders"

echo "Configuration:"
echo "  Concurrent Users: $CONCURRENT_USERS"
echo "  Test Duration: ${TEST_DURATION}s"
echo "  Target Endpoint: $ORDER_ENDPOINT"
echo ""

# Check if services are running
echo "🔍 Checking service availability..."
services=("localhost:8000" "localhost:8001" "localhost:8002" "localhost:8003" "localhost:8004" "localhost:9000")

for service in "${services[@]}"; do
    if curl -s -f "http://$service/health" > /dev/null; then
        echo "✅ $service is healthy"
    else
        echo "❌ $service is not available"
        exit 1
    fi
done

# Prepare test data
echo "📊 Preparing test data..."
python scripts/test_data_generator.py --customers 100 --products 200 --orders 0

# Get test customers and products
echo "📦 Loading test entities..."
CUSTOMER_ID=$(python -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
async def get_customer():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client.ecommerce_saga
    customer = await db.customers.find_one()
    print(customer['customer_id'])
    client.close()
asyncio.run(get_customer())
")

PRODUCT_ID=$(python -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
async def get_product():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client.ecommerce_saga
    product = await db.inventory.find_one({'status': 'AVAILABLE', 'quantity': {'\\$gt': 100}})
    print(product['product_id'])
    client.close()
asyncio.run(get_product())
")

echo "Using Customer ID: $CUSTOMER_ID"
echo "Using Product ID: $PRODUCT_ID"

# Create temporary test script
cat > /tmp/order_test.js << EOF
import http from 'k6/http';
import { check, sleep } from 'k6';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

export let options = {
  stages: [
    { duration: '10s', target: $CONCURRENT_USERS },
    { duration: '${TEST_DURATION}s', target: $CONCURRENT_USERS },
    { duration: '10s', target: 0 },
  ],
};

export default function() {
  const orderData = {
    customer_id: '$CUSTOMER_ID',
    items: [
      {
        product_id: '$PRODUCT_ID',
        quantity: 1,
        price: 29.99
      }
    ],
    shipping_address: {
      street: '123 Test St',
      city: 'Test City',
      state: 'TS',
      zip_code: '12345',
      country: 'US'
    },
    payment_method: 'CREDIT_CARD'
  };

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Correlation-ID': uuidv4(),
    },
  };

  const response = http.post('$ORDER_ENDPOINT', JSON.stringify(orderData), params);
  
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 30s': (r) => r.timings.duration < 30000,
    'order_id present': (r) => JSON.parse(r.body).order_id !== undefined,
  });

  sleep(1);
}
EOF

# Run performance test if k6 is available
if command -v k6 &> /dev/null; then
    echo "🏃 Running performance test with k6..."
    k6 run /tmp/order_test.js
else
    echo "⚠️  k6 not found, running basic curl test..."
    
    # Alternative basic test using curl
    echo "🏃 Running basic concurrent test..."
    
    # Function to create order
    create_order() {
        local correlation_id=$(uuidgen)
        curl -s -X POST "$ORDER_ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "X-Correlation-ID: $correlation_id" \
            -d "{
                \"customer_id\": \"$CUSTOMER_ID\",
                \"items\": [{
                    \"product_id\": \"$PRODUCT_ID\",
                    \"quantity\": 1,
                    \"price\": 29.99
                }],
                \"shipping_address\": {
                    \"street\": \"123 Test St\",
                    \"city\": \"Test City\",
                    \"state\": \"TS\",
                    \"zip_code\": \"12345\",
                    \"country\": \"US\"
                },
                \"payment_method\": \"CREDIT_CARD\"
            }" \
            -w "%{http_code},%{time_total}\n" \
            -o /dev/null
    }
    
    # Run concurrent requests
    echo "Sending $CONCURRENT_USERS concurrent requests..."
    
    for ((i=1; i<=CONCURRENT_USERS; i++)); do
        create_order &
    done
    
    wait
    echo "Basic concurrent test completed"
fi

# Clean up
rm -f /tmp/order_test.js

# Generate performance report
echo "📈 Generating performance report..."
python scripts/log_analyzer.py --report performance --hours 1

echo "✅ Performance test completed!" 
# E-Commerce Order Management with Saga Pattern

This project demonstrates a microservices-based e-commerce backend where the **order processing** flow is handled using the **Saga pattern with orchestration**.

## Overview

When a user places an order, a distributed transaction occurs across multiple services, orchestrated using the Saga pattern to ensure data consistency across microservices.

## Architecture

### System Components

```mermaid
flowchart TB
    Client((Client))-->OrderService
    subgraph Microservices
        OrderService-->Coordinator
        Coordinator(Order Saga Coordinator)
        Coordinator-->Inventory
        Coordinator-->Payment
        Coordinator-->Shipping
        Coordinator-->Notification

        OrderService([Order Service])
        Inventory([Inventory Service])
        Payment([Payment Service])
        Shipping([Shipping Service])
        Notification([Notification Service])

        DB[(MongoDB)]
        OrderService---DB
        Inventory---DB
        Payment---DB
        Shipping---DB
        Notification---DB
    end

    classDef coordinator fill: ,stroke:#333,stroke-width:2px
    classDef database fill: #185683,stroke:#333,stroke-width:1px
    classDef service fill: #106c10,stroke:#333,stroke-width:1px
    class Coordinator coordinator
    class DB database
    class OrderService,Inventory,Payment,Shipping,Notification service
```

### Service Roles

| Service | Role | Key Operations |
|---------|------|----------------|
| Order Service | Creates and manages orders | Create, Cancel, Update order status |
| Order Saga Coordinator | Orchestrates the distributed transaction | Execute saga steps, Handle compensations |
| Inventory Service | Manages product inventory | Reserve, Release items |
| Payment Service | Handles payment processing | Process payment, Issue refund |
| Shipping Service | Manages order delivery | Schedule, Cancel delivery |
| Notification Service | Sends user notifications | Order confirmation, Status updates |

## Saga Pattern Implementation

### Sequence Flow

```mermaid
sequenceDiagram
    autonumber
    actor C as Client
    participant OS as Order Service
    participant SC as Saga Coordinator
    participant IS as Inventory Service
    participant PS as Payment Service
    participant SS as Shipping Service
    participant NS as Notification Service
    
    C->>+OS: Place Order
    OS->>+SC: Start Order Saga
    
    rect rgb(10, 104, 2)
    Note over SC,IS: Step 1: Reserve Inventory
    SC->>IS: Reserve Items
    alt Success
        IS-->>SC: Items Reserved
        
        Note over SC,PS: Step 2: Process Payment
        SC->>PS: Process Payment
        alt Success
            PS-->>SC: Payment Completed
            
            Note over SC,SS: Step 3: Schedule Shipping
            SC->>SS: Schedule Delivery
            alt Success
                SS-->>SC: Delivery Scheduled
                
                Note over SC,NS: Step 4: Send Notification
                SC->>NS: Send Confirmation
                NS-->>SC: Notification Sent
                SC-->>-OS: Order Completed
                OS-->>-C: Order Success
            else Shipping Failed
                SS-->>SC: Error
                SC->>PS: Refund Payment
                SC->>IS: Release Items
                SC-->>OS: Order Failed
                OS-->>C: Order Failed (Shipping)
            end
        else Payment Failed
            PS-->>SC: Error
            SC->>IS: Release Items
            SC-->>OS: Order Failed
            OS-->>C: Order Failed (Payment)
        end
    else Inventory Failed
        IS-->>SC: Error
        SC-->>OS: Order Failed
        OS-->>C: Order Failed (Inventory)
    end
    end
```

### Compensation Mechanism

The Saga pattern ensures data consistency by defining compensating actions for each step:

1. **Order Creation**
   - Action: Create order record
   - Compensation: Cancel order

2. **Inventory Reservation**
   - Action: Reserve items
   - Compensation: Release reserved items

3. **Payment Processing**
   - Action: Charge payment
   - Compensation: Issue refund

4. **Shipping Scheduling**
   - Action: Schedule delivery
   - Compensation: Cancel shipping

5. **Notification** (Optional)
   - Action: Send confirmation
   - Compensation: Send cancellation notice

## Deployment Architecture

```mermaid
graph TB
    subgraph OpenShift["OpenShift Container Platform"]
        subgraph Project["e-commerce-saga namespace"]
            Route["OpenShift Routes"]
            
            subgraph Services["Kubernetes Services"]
                SVC1["order-svc"]
                SVC2["inventory-svc"]
                SVC3["payment-svc"]
                SVC4["shipping-svc"]
                SVC5["notification-svc"]
            end
            
            subgraph Pods["Application Pods"]
                direction LR
                POD1["order-pod"]
                POD2["inventory-pod"]
                POD3["payment-pod"]
                POD4["shipping-pod"]
                POD5["notification-pod"]
            end
            
            subgraph Storage["Persistent Storage"]
                MongoDB[(MongoDB)]
            end
            
            Route --> Services
            Services --> Pods
            Pods --> MongoDB
        end
    end
    
    Client((Client)) --> Route
    
    classDef openshift fill: #0846c3,stroke:#fff,stroke-width:1px,color:#fff
    classDef project fill:#0a83ba,stroke:#fff,stroke-width:1px,color:#fff
    classDef storage fill:#9cb307,stroke:#fff,stroke-width:1px,color:#fff
    classDef client fill:#396b07,stroke:#fff,stroke-width:1px,color:#fff
    
    class OpenShift openshift
    class Project project
    class Storage,MongoDB storage
    class Client client
```

## Technical Details

### Tech Stack

- **Language**: Python 3.11
- **Framework**: FastAPI
  - High-performance async web framework
  - Automatic OpenAPI/Swagger documentation
  - Built-in request/response validation
- **Database**: MongoDB
  - Document-based NoSQL database
  - Perfect for microservices with flexible schemas
  - Async driver support
- **Containerization**: 
  - Podman/Docker for containerization
  - Multi-stage builds for optimized images
  - Shared base image for common dependencies
- **Deployment**: 
  - OpenShift Container Platform
  - Helm charts for orchestrated deployment
  - Auto-scaling and high availability

### Key Implementation Features

1. **Saga Pattern Implementation**
   ```python
   class Saga:
       def __init__(self, saga_id: str, description: str = ""):
           self.id = saga_id
           self.steps: List[SagaStep] = []
           self.status = SagaStatus.STARTED
           self.context: Dict[str, Any] = {"saga_id": saga_id}
   ```

2. **Asynchronous Communication**
   - HTTP-based service communication
   - Async/await for non-blocking operations
   - Retry mechanisms for resilience

3. **Error Handling**
   - Comprehensive compensation logic
   - Transaction rollback on failures
   - Detailed error tracking and logging

4. **Monitoring & Observability**
   - OpenAPI documentation at `/docs`
   - Status endpoints for each service
   - Transaction tracing via saga_id

## Getting Started

### Prerequisites

- Python 3.11+
- MongoDB
- Podman or Docker
- OpenShift Local (formerly CRC)

### Running Locally with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check running services
docker-compose ps
```

### Running Locally with Podman

```bash
# Install dependencies
pip install -r common/requirements.txt

# Start MongoDB with Podman
podman run -d -p 27017:27017 --name saga-mongodb mongo:latest

# Run the services
./run-local.sh
```

### Deploying to OpenShift Local

#### 1. Prerequisites

- OpenShift Local installed and running
- `oc` CLI installed and configured
- Podman installed
- Helm installed

#### 2. Start OpenShift Local

```bash
# Start OpenShift Local (CRC)
crc start

# Login to OpenShift
oc login -u developer -p developer
```

#### 3. Automatic Deployment

The easiest way to deploy is using our automated script:

```bash
# Make the script executable
chmod +x deploy-openshift.sh

# Run the deployment script
./deploy-openshift.sh
```

This script will:
1. Build container images using Podman
2. Push images to the OpenShift registry
3. Deploy the application using Helm
4. Display the routes to access the services

#### 4. Manual Deployment

If you prefer to deploy manually:

```bash
# Build images with Podman
./build-podman.sh

# Push images to OpenShift registry
./push-to-openshift.sh

# Deploy using Helm
REGISTRY=$(oc get route default-route -n openshift-image-registry --template='{{ .spec.host }}')
helm install e-commerce-saga ./helm --set global.imageRegistry=$REGISTRY/e-commerce-saga
```

#### 5. Accessing the Application

After deployment, you can access the services through their OpenShift routes:

```bash
# Get the routes
oc get routes
```

The API documentation is available at the `/docs` endpoint of each service.

## API Documentation

Each service provides a SwaggerUI interface at `/docs` endpoint for interactive API testing.

### Order Service (Port 8000)

#### Public Endpoints
- `POST /api/orders`
  - Create a new order and start saga
  - Request: Order details with items, payment, shipping info
  - Response: Saga ID and order status

- `GET /api/orders/{order_id}`
  - Get order details with saga status
  - Response: Complete order details with transaction history

- `GET /api/orders`
  - List orders with pagination
  - Query params: customer_id, status, limit, skip

#### Saga Endpoints
- `POST /api/orders/create` - Create order record (saga)
- `POST /api/orders/cancel` - Cancel order (compensation)

### Inventory Service (Port 8001)

#### Public Endpoints
- `GET /api/inventory`
  - List available inventory
  - Query params: category, inStock, limit, skip

- `GET /api/inventory/{product_id}`
  - Get product inventory details
  - Response: Stock levels, reservations

#### Saga Endpoints
- `POST /api/inventory/reserve` - Reserve inventory items
- `POST /api/inventory/release` - Release reservation (compensation)

### Payment Service (Port 8002)

#### Public Endpoints
- `GET /api/payments`
  - List payments with filtering
  - Query params: customer_id, status, date_range

- `GET /api/payments/{payment_id}`
  - Get payment transaction details
  - Response: Payment status, method, amount

#### Saga Endpoints
- `POST /api/payments/process` - Process payment
- `POST /api/payments/refund` - Issue refund (compensation)

### Shipping Service (Port 8003)

#### Public Endpoints
- `GET /api/shipping`
  - List shipments
  - Query params: customer_id, status, date_range

- `GET /api/shipping/{shipping_id}`
  - Get shipping details
  - Response: Tracking info, delivery status

#### Saga Endpoints
- `POST /api/shipping/schedule` - Schedule delivery
- `POST /api/shipping/cancel` - Cancel shipping (compensation)

### Notification Service (Port 8004)

#### Public Endpoints
- `GET /api/notifications`
  - List notifications
  - Query params: customer_id, type, read_status

- `GET /api/notifications/{notification_id}`
  - Get notification details
  - Response: Message content, timestamp

#### Saga Endpoints
- `POST /api/notifications/send` - Send notification
- `POST /api/notifications/cancel` - Cancel notification (compensation)

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
# Backend Architecture Patterns

Microservices, event-driven architecture, scalability patterns (2025).

## Monolith vs Microservices

### Monolithic Architecture

```
┌─────────────────────────────────┐
│      Single Application         │
│                                 │
│  ┌─────────┐  ┌──────────┐    │
│  │  Users  │  │ Products │    │
│  └─────────┘  └──────────┘    │
│  ┌─────────┐  ┌──────────┐    │
│  │ Orders  │  │ Payments │    │
│  └─────────┘  └──────────┘    │
│                                 │
│     Single Database             │
└─────────────────────────────────┘
```

**Pros:**
- Simple to develop and deploy
- Easy local testing
- Single codebase
- Strong consistency (ACID transactions)

**Cons:**
- Tight coupling
- Scaling limitations
- Deployment risk (all-or-nothing)
- Tech stack lock-in

**When to Use:** Startups, MVPs, small teams, unclear domain boundaries

### Microservices Architecture

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  User    │   │ Product  │   │  Order   │   │ Payment  │
│ Service  │   │ Service  │   │ Service  │   │ Service  │
└────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
     │              │              │              │
  ┌──▼──┐        ┌──▼──┐        ┌──▼──┐        ┌──▼──┐
  │  DB │        │  DB │        │  DB │        │  DB │
  └─────┘        └─────┘        └─────┘        └─────┘
```

**Pros:**
- Independent deployment
- Technology flexibility
- Fault isolation
- Easier scaling (scale services independently)

**Cons:**
- Complex deployment
- Distributed system challenges (network latency, partial failures)
- Data consistency (eventual consistency)
- Operational overhead

**When to Use:** Large teams, clear domain boundaries, need independent scaling, tech diversity

## Microservices Patterns

### Database per Service Pattern

**Concept:** Each service owns its database

```
User Service → User DB (PostgreSQL)
Product Service → Product DB (MongoDB)
Order Service → Order DB (PostgreSQL)
```

**Benefits:**
- Service independence
- Technology choice per service
- Fault isolation

**Challenges:**
- No joins across services
- Distributed transactions
- Data duplication

### API Gateway Pattern

```
Client
  │
  ▼
┌─────────────────┐
│  API Gateway    │  - Authentication
│  (Kong/NGINX)   │  - Rate limiting
└────────┬────────┘  - Request routing
         │
    ┌────┴────┬────────┬────────┐
    ▼         ▼        ▼        ▼
  User    Product   Order   Payment
 Service  Service  Service  Service
```

**Responsibilities:**
- Request routing
- Authentication/authorization
- Rate limiting
- Request/response transformation
- Caching

**Implementation (Kong):**
```yaml
services:
  - name: user-service
    url: http://user-service:3000
    routes:
      - name: user-route
        paths:
          - /api/users

  - name: product-service
    url: http://product-service:3001
    routes:
      - name: product-route
        paths:
          - /api/products

plugins:
  - name: rate-limiting
    config:
      minute: 100
  - name: jwt
```

### Service Discovery

**Concept:** Services find each other dynamically

```typescript
// Consul service discovery
import Consul from 'consul';

const consul = new Consul();

// Register service
await consul.agent.service.register({
  name: 'user-service',
  address: '192.168.1.10',
  port: 3000,
  check: {
    http: 'http://192.168.1.10:3000/health',
    interval: '10s',
  },
});

// Discover service
const services = await consul.catalog.service.nodes('product-service');
const productServiceUrl = `http://${services[0].ServiceAddress}:${services[0].ServicePort}`;
```

### Circuit Breaker Pattern

**Concept:** Stop calling failing service, prevent cascade failures

```typescript
import CircuitBreaker from 'opossum';

const breaker = new CircuitBreaker(callExternalService, {
  timeout: 3000, // 3s timeout
  errorThresholdPercentage: 50, // Open circuit after 50% failures
  resetTimeout: 30000, // Try again after 30s
});

breaker.on('open', () => {
  console.log('Circuit breaker opened!');
});

breaker.fallback(() => ({
  data: 'fallback-response',
  source: 'cache',
}));

const result = await breaker.fire(requestParams);
```

**States:**
- **Closed:** Normal operation, requests go through
- **Open:** Too many failures, requests fail immediately
- **Half-Open:** Testing if service recovered

### Saga Pattern (Distributed Transactions)

**Choreography-Based Saga:**
```
Order Service: Create Order → Publish "OrderCreated"
                                    ↓
Payment Service: Reserve Payment → Publish "PaymentReserved"
                                    ↓
Inventory Service: Reserve Stock → Publish "StockReserved"
                                    ↓
Shipping Service: Create Shipment → Publish "ShipmentCreated"

If any step fails → Compensating transactions (rollback)
```

**Orchestration-Based Saga:**
```
Saga Orchestrator
    ↓ Create Order
Order Service
    ↓ Reserve Payment
Payment Service
    ↓ Reserve Stock
Inventory Service
    ↓ Create Shipment
Shipping Service
```


---

Continued in [backend-architecture-cont.md](backend-architecture-cont.md)

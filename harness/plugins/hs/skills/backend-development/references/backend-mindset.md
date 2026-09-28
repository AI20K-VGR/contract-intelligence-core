# Backend Development Mindset

Problem-solving, architectural thinking, collaboration patterns for backend engineers (2025).

## Problem-Solving Mindset

### Systems Thinking Approach

**Holistic Engineering** - how components interact within larger ecosystem

```
User Request
  → Load Balancer
  → API Gateway (auth, rate limiting)
  → Application (business logic)
  → Cache Layer (Redis)
  → Database (persistent storage)
  → Message Queue (async processing)
  → External Services
```

**Questions to Ask:**
- What happens if this component fails?
- How does this scale under load?
- What are the dependencies?
- Where are the bottlenecks?
- What's the blast radius of changes?

### Breaking Down Complex Problems

**Decomposition Strategy:**

1. **Understand requirements** - What problem are we solving?
2. **Identify constraints** - Performance, budget, timeline, tech stack
3. **Break into modules** - Separate concerns (auth, data, business logic)
4. **Define interfaces** - API contracts between modules
5. **Prioritize** - Critical path first
6. **Iterate** - Build, test, refine

**Example: Building Payment System**

```
Complex: "Build payment processing"

Decomposed:
1. Payment gateway integration (Stripe/PayPal)
2. Order creation and validation
3. Payment intent creation
4. Webhook handling (success/failure)
5. Idempotency (prevent double charges)
6. Retry logic for transient failures
7. Audit logging
8. Refund processing
9. Reconciliation system
```

## Trade-Off Analysis

### CAP Theorem (Choose 2 of 3)

**Consistency** - All nodes see same data at same time
**Availability** - Every request receives response
**Partition Tolerance** - System works despite network failures

**Real-World Choices:**
- **CP (Consistency + Partition Tolerance):** Banking systems, financial transactions
- **AP (Availability + Partition Tolerance):** Social media feeds, product catalogs
- **CA (Consistency + Availability):** Single-node databases (not distributed)

### PACELC Extension

**If Partition:** Choose Availability or Consistency
**Else (no partition):** Choose Latency or Consistency

**Examples:**
- **PA/EL:** Cassandra (available during partition, low latency normally)
- **PC/EC:** HBase (consistent during partition, consistent over latency)
- **PA/EC:** DynamoDB (configurable consistency vs latency)

### Performance vs Maintainability

| Optimize For | When to Choose |
|--------------|---------------|
| **Performance** | Hot paths, high-traffic endpoints, real-time systems |
| **Maintainability** | Internal tools, admin dashboards, CRUD operations |
| **Both** | Core business logic, payment processing, authentication |

**Example:**
```typescript
// Maintainable: Readable, easy to debug
const users = await db.users.findAll({
  where: { active: true },
  include: ['posts', 'comments'],
});

// Performant: Optimized query, reduced joins
const users = await db.query(`
  SELECT u.*,
    (SELECT COUNT(*) FROM posts WHERE user_id = u.id) as post_count,
    (SELECT COUNT(*) FROM comments WHERE user_id = u.id) as comment_count
  FROM users u
  WHERE u.active = true
`);
```

### Technical Debt Management

**20-40% productivity increase** from addressing technical debt properly

**Debt Quadrants:**
1. **Reckless + Deliberate:** "We don't have time for design"
2. **Reckless + Inadvertent:** "What's layering?"
3. **Prudent + Deliberate:** "Ship now, refactor later" (acceptable)
4. **Prudent + Inadvertent:** "Now we know better" (acceptable)

**Prioritization:**
- High interest, high impact → Fix immediately
- High interest, low impact → Schedule in sprint
- Low interest, high impact → Tech debt backlog
- Low interest, low impact → Leave as-is

## Architectural Thinking

### Domain-Driven Design (DDD)

**Bounded Contexts** - Separate models for different domains

```
E-commerce System:

[Sales Context]          [Inventory Context]       [Shipping Context]
- Order (id, items,      - Product (id, stock,     - Shipment (id,
  total, customer)        location, reserved)       address, status)
- Customer (id, email)   - Warehouse (id, name)    - Carrier (name, API)
- Payment (status)       - StockLevel (quantity)   - Tracking (number)

Each context has its own:
- Data model
- Business rules
- Database schema
- API contracts
```

**Ubiquitous Language** - shared dev/domain-expert vocabulary

### Layered Architecture (Separation of Concerns)

```
┌─────────────────────────────┐
│   Presentation Layer        │  Controllers, Routes, DTOs
│   (API endpoints)           │
├─────────────────────────────┤
│   Business Logic Layer      │  Services, Use Cases, Domain Logic
│   (Core logic)              │
├─────────────────────────────┤
│   Data Access Layer         │  Repositories, ORMs, Database
│   (Persistence)             │
└─────────────────────────────┘
```

**Benefits:**
- Clear responsibilities
- Easier testing (mock layers)
- Flexibility to change implementations
- Reduced coupling

### Designing for Failure (Resilience)

**Assume everything fails eventually**

**Patterns:**
1. **Circuit Breaker** - Stop calling failing service
2. **Retry with Backoff** - Exponential delay between retries
3. **Timeout** - Don't wait forever
4. **Fallback** - Graceful degradation
5. **Bulkhead** - Isolate failures (resource pools)

```typescript
import { CircuitBreaker } from 'opossum';

const breaker = new CircuitBreaker(externalAPICall, {
  timeout: 3000, // 3s timeout
  errorThresholdPercentage: 50, // Open after 50% failures
  resetTimeout: 30000, // Try again after 30s
});

breaker.fallback(() => ({ data: 'cached-response' }));

const result = await breaker.fire(requestParams);
```


---

Continued in [backend-mindset-cont.md](backend-mindset-cont.md)

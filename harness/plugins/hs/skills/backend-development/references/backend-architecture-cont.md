# Backend Architecture Patterns (continued 2/2)

## Event-Driven Architecture

**Impact:** 85% organizations recognize business value

### Event Sourcing

**Concept:** Store events, not current state

```typescript
// Traditional: Store current state
{
  userId: '123',
  balance: 500
}

// Event Sourcing: Store events
[
  { type: 'AccountCreated', userId: '123', timestamp: '...' },
  { type: 'MoneyDeposited', amount: 1000, timestamp: '...' },
  { type: 'MoneyWithdrawn', amount: 500, timestamp: '...' },
]

// Reconstruct state by replaying events
const balance = events
  .filter(e => e.userId === '123')
  .reduce((acc, event) => {
    if (event.type === 'MoneyDeposited') return acc + event.amount;
    if (event.type === 'MoneyWithdrawn') return acc - event.amount;
    return acc;
  }, 0);
```

**Benefits:**
- Complete audit trail
- Temporal queries (state at any point in time)
- Event replay for debugging
- Flexible projections

### Message Broker Patterns

**Kafka (Event Streaming):**
```typescript
import { Kafka } from 'kafkajs';

const kafka = new Kafka({
  clientId: 'order-service',
  brokers: ['kafka:9092'],
});

// Producer
const producer = kafka.producer();
await producer.send({
  topic: 'order-events',
  messages: [
    {
      key: order.id,
      value: JSON.stringify({
        type: 'OrderCreated',
        orderId: order.id,
        userId: order.userId,
        total: order.total,
      }),
    },
  ],
});

// Consumer
const consumer = kafka.consumer({ groupId: 'inventory-service' });
await consumer.subscribe({ topic: 'order-events' });
await consumer.run({
  eachMessage: async ({ topic, partition, message }) => {
    const event = JSON.parse(message.value.toString());
    if (event.type === 'OrderCreated') {
      await reserveInventory(event.orderId);
    }
  },
});
```

**RabbitMQ (Task Queues):**
```typescript
import amqp from 'amqplib';

const connection = await amqp.connect('amqp://localhost');
const channel = await connection.createChannel();

// Producer
await channel.assertQueue('email-queue', { durable: true });
channel.sendToQueue('email-queue', Buffer.from(JSON.stringify({
  to: user.email,
  subject: 'Welcome!',
  body: 'Thank you for signing up',
})));

// Consumer
await channel.consume('email-queue', async (msg) => {
  const emailData = JSON.parse(msg.content.toString());
  await sendEmail(emailData);
  channel.ack(msg);
});
```

## CQRS (Command Query Responsibility Segregation)

**Concept:** Separate read and write models

```
Write Side (Commands):           Read Side (Queries):
CreateOrder                      GetOrderById
UpdateOrder                      GetUserOrders
  ↓                                ↑
┌─────────┐                    ┌─────────┐
│ Write   │ → Events →         │  Read   │
│  DB     │    (sync)          │  DB     │
│(Postgres)                    │(MongoDB)│
└─────────┘                    └─────────┘
```

**Benefits:**
- Optimized read models
- Scalable (scale reads independently)
- Flexible (different DB for reads/writes)

**Implementation:**
```typescript
// Command (Write)
class CreateOrderCommand {
  constructor(public userId: string, public items: OrderItem[]) {}
}

class CreateOrderHandler {
  async execute(command: CreateOrderCommand) {
    const order = await Order.create(command);
    await eventBus.publish(new OrderCreatedEvent(order));
    return order.id;
  }
}

// Query (Read)
class GetOrderQuery {
  constructor(public orderId: string) {}
}

class GetOrderHandler {
  async execute(query: GetOrderQuery) {
    // Read from optimized read model
    return await OrderReadModel.findById(query.orderId);
  }
}
```

## Scalability Patterns

### Horizontal Scaling (Scale Out)

```
Load Balancer
    ↓
┌───┴───┬───────┬───────┐
│ App 1 │ App 2 │ App 3 │ ... App N
└───┬───┴───┬───┴───┬───┘
    └───────┴───────┘
         ↓
    Shared Database
    (with read replicas)
```

### Database Sharding

**Range-Based Sharding:**
```
Users 1-1M     → Shard 1
Users 1M-2M    → Shard 2
Users 2M-3M    → Shard 3
```

**Hash-Based Sharding:**
```typescript
function getShardId(userId: string): number {
  const hash = crypto.createHash('md5').update(userId).digest('hex');
  return parseInt(hash.substring(0, 8), 16) % SHARD_COUNT;
}

const shardId = getShardId(userId);
const db = shards[shardId];
const user = await db.users.findById(userId);
```

### Caching Layers

```
Client
  → CDN (static assets)
  → API Gateway Cache (public endpoints)
  → Application Cache (Redis - user sessions, hot data)
  → Database Query Cache
  → Database
```

## Architecture Decision Matrix

| Pattern | When to Use | Complexity | Benefits |
|---------|-------------|------------|----------|
| **Monolith** | Small team, MVP, unclear boundaries | Low | Simple, fast development |
| **Microservices** | Large team, clear domains, need scaling | High | Independent deployment, fault isolation |
| **Event-Driven** | Async workflows, audit trail needed | Moderate | Decoupling, scalability |
| **CQRS** | Different read/write patterns | High | Optimized queries, scalability |
| **Serverless** | Spiky traffic, event-driven | Low | Auto-scaling, pay-per-use |

## Anti-Patterns to Avoid

1. **Distributed Monolith** - Microservices that all depend on each other
2. **Chatty Services** - Too many inter-service calls (network overhead)
3. **Shared Database** - Microservices sharing same DB (tight coupling)
4. **Over-Engineering** - Using microservices for small apps
5. **No Circuit Breakers** - Cascade failures in distributed systems

## Architecture Checklist

- [ ] Clear service boundaries (domain-driven design)
- [ ] Database per service (no shared databases)
- [ ] API Gateway for client requests
- [ ] Service discovery configured
- [ ] Circuit breakers for resilience
- [ ] Event-driven communication (Kafka/RabbitMQ)
- [ ] CQRS for read-heavy systems
- [ ] Distributed tracing (Jaeger/OpenTelemetry)
- [ ] Health checks for all services
- [ ] Horizontal scaling capability

## Resources

- **Microservices Patterns:** https://microservices.io/patterns/
- **Martin Fowler - Microservices:** https://martinfowler.com/articles/microservices.html
- **Event-Driven Architecture:** https://aws.amazon.com/event-driven-architecture/
- **CQRS Pattern:** https://martinfowler.com/bliki/CQRS.html

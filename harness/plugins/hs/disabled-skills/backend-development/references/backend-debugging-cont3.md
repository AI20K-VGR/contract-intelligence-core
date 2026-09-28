# Backend Debugging Strategies (continued 4/4)

## Common Debugging Scenarios

### 1. High CPU Usage

**Steps:**
1. Profile CPU (flamegraph)
2. Identify hot functions
3. Check for:
   - Infinite loops
   - Heavy regex operations
   - Inefficient algorithms (O(n²))
   - Blocking operations in event loop (Node.js)

**Node.js Example:**
```typescript
// ❌ Bad: Blocking event loop
function fibonacci(n) {
  if (n <= 1) return n;
  return fibonacci(n - 1) + fibonacci(n - 2); // Exponential time
}

// ✅ Good: Memoized or iterative
const memo = new Map();
function fibonacciMemo(n) {
  if (n <= 1) return n;
  if (memo.has(n)) return memo.get(n);
  const result = fibonacciMemo(n - 1) + fibonacciMemo(n - 2);
  memo.set(n, result);
  return result;
}
```

### 2. Memory Leaks

**Symptoms:**
- Memory usage grows over time
- Eventually crashes (OOM)
- Performance degradation

**Common Causes:**
```typescript
// ❌ Memory leak: Event listeners not removed
class DataService {
  constructor(eventBus) {
    eventBus.on('data', (data) => this.processData(data));
    // Listener never removed, holds reference to DataService
  }
}

// ✅ Fix: Remove listeners
class DataService {
  constructor(eventBus) {
    this.eventBus = eventBus;
    this.handler = (data) => this.processData(data);
    eventBus.on('data', this.handler);
  }

  destroy() {
    this.eventBus.off('data', this.handler);
  }
}

// ❌ Memory leak: Global cache without limits
const cache = new Map();
function getCachedData(key) {
  if (!cache.has(key)) {
    cache.set(key, expensiveOperation(key)); // Grows forever
  }
  return cache.get(key);
}

// ✅ Fix: LRU cache with size limit
import LRU from 'lru-cache';
const cache = new LRU({ max: 1000, ttl: 1000 * 60 * 60 });
```

**Detection:**
```bash
# Node.js: Check heap size over time
node --expose-gc --max-old-space-size=4096 app.js

# Take periodic heap snapshots
# Compare snapshots in Chrome DevTools
```

### 3. Slow Database Queries

**Steps:**
1. Enable slow query log
2. Analyze with EXPLAIN
3. Add indexes
4. Optimize query

**PostgreSQL Example:**
```sql
-- Before: Slow full table scan
SELECT * FROM orders
WHERE user_id = 123
ORDER BY created_at DESC
LIMIT 10;

-- EXPLAIN shows: Seq Scan on orders

-- Fix: Add index
CREATE INDEX idx_orders_user_id_created_at
ON orders(user_id, created_at DESC);

-- After: Index Scan using idx_orders_user_id_created_at
-- 100x faster
```

### 4. Connection Pool Exhaustion

**Symptoms:**
- "Connection pool exhausted" errors
- Requests hang indefinitely
- Database connections at max

**Causes & Fixes:**
```typescript
// ❌ Bad: Connection leak
async function getUser(id) {
  const client = await pool.connect();
  const result = await client.query('SELECT * FROM users WHERE id = $1', [id]);
  return result.rows[0];
  // Connection never released!
}

// ✅ Good: Always release
async function getUser(id) {
  const client = await pool.connect();
  try {
    const result = await client.query('SELECT * FROM users WHERE id = $1', [id]);
    return result.rows[0];
  } finally {
    client.release(); // Always release
  }
}

// ✅ Better: Use pool directly
async function getUser(id) {
  const result = await pool.query('SELECT * FROM users WHERE id = $1', [id]);
  return result.rows[0];
  // Automatically releases
}
```

### 5. Race Conditions

**Example:**
```typescript
// ❌ Bad: Race condition
let counter = 0;

async function incrementCounter() {
  const current = counter; // Thread 1 reads 0
  await doSomethingAsync(); // Thread 2 reads 0
  counter = current + 1; // Thread 1 writes 1, Thread 2 writes 1
  // Expected: 2, Actual: 1
}

// ✅ Fix: Atomic operations (Redis)
async function incrementCounter() {
  return await redis.incr('counter');
  // Atomic, thread-safe
}

// ✅ Fix: Database transactions
async function incrementCounter(userId) {
  await db.transaction(async (trx) => {
    const user = await trx('users')
      .where({ id: userId })
      .forUpdate() // Row-level lock
      .first();

    await trx('users')
      .where({ id: userId })
      .update({ counter: user.counter + 1 });
  });
}
```

## Debugging Checklist

**Before Diving Into Code:**
- [ ] Read error message completely
- [ ] Check logs for context
- [ ] Reproduce the issue reliably
- [ ] Isolate the problem (binary search)
- [ ] Verify assumptions

**Investigation:**
- [ ] Enable debug logging
- [ ] Add strategic log points
- [ ] Use debugger breakpoints
- [ ] Profile performance if slow
- [ ] Check database queries
- [ ] Monitor system resources

**Production Issues:**
- [ ] Check APM dashboards
- [ ] Review distributed traces
- [ ] Analyze error rates
- [ ] Compare with previous baseline
- [ ] Check for recent deployments
- [ ] Review infrastructure changes

**After Fix:**
- [ ] Verify fix in development
- [ ] Add regression test
- [ ] Document the issue
- [ ] Deploy with monitoring
- [ ] Confirm fix in production

## Debugging Resources

**Tools:**
- Node.js: https://nodejs.org/en/docs/guides/debugging-getting-started/
- Chrome DevTools: https://developer.chrome.com/docs/devtools/
- Clinic.js: https://clinicjs.org/
- Sentry: https://docs.sentry.io/
- DataDog: https://docs.datadoghq.com/
- New Relic: https://docs.newrelic.com/

**Best Practices:**
- 12 Factor App Logs: https://12factor.net/logs
- Google SRE Book: https://sre.google/sre-book/table-of-contents/
- OpenTelemetry: https://opentelemetry.io/docs/

**Database:**
- PostgreSQL EXPLAIN: https://www.postgresql.org/docs/current/using-explain.html
- MongoDB Performance: https://www.mongodb.com/docs/manual/administration/analyzing-mongodb-performance/

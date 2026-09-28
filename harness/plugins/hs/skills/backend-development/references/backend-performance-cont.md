# Backend Performance & Scalability (continued 2/2)

## Database Scaling Patterns

### Read Replicas

```
Primary (Write) → Replica 1 (Read)
               → Replica 2 (Read)
               → Replica 3 (Read)
```

**Implementation:**
```typescript
// Write to primary
await primaryDb.users.create(userData);

// Read from replica
const users = await replicaDb.users.findAll();
```

**Use Cases:**
- Read-heavy workloads (90%+ reads)
- Analytics queries
- Reporting dashboards

### Database Sharding

**Horizontal Partitioning** - Split data across databases

```typescript
// Shard by user ID
function getShardId(userId: string): number {
  return hashCode(userId) % SHARD_COUNT;
}

const shardId = getShardId(userId);
const db = shards[shardId];
const user = await db.users.findById(userId);
```

**Sharding Strategies:**
- **Range-based:** Users 1-1M → Shard 1, 1M-2M → Shard 2
- **Hash-based:** Hash(userId) % shard_count
- **Geographic:** EU users → EU shard, US users → US shard
- **Entity-based:** Users → Shard 1, Orders → Shard 2

## Performance Monitoring

### Key Metrics

**Application:**
- Response time (p50, p95, p99)
- Throughput (requests/second)
- Error rate
- CPU/memory usage

**Database:**
- Query execution time
- Connection pool saturation
- Cache hit rate
- Slow query log

**Tools:**
- Prometheus + Grafana (metrics)
- New Relic / Datadog (APM)
- Sentry (error tracking)
- OpenTelemetry (distributed tracing)

## Performance Optimization Checklist

### Database
- [ ] Indexes on frequently queried columns
- [ ] Connection pooling configured
- [ ] N+1 queries eliminated
- [ ] Slow query log monitored
- [ ] Query execution plans analyzed

### Caching
- [ ] Redis cache for hot data
- [ ] Cache TTL configured appropriately
- [ ] Cache invalidation on writes
- [ ] CDN for static assets
- [ ] >80% cache hit rate achieved

### Application
- [ ] Async processing for long tasks
- [ ] Response compression enabled (gzip)
- [ ] Load balancing configured
- [ ] Health checks implemented
- [ ] Resource limits set (CPU, memory)

### Monitoring
- [ ] APM tool configured (New Relic/Datadog)
- [ ] Error tracking (Sentry)
- [ ] Performance dashboards (Grafana)
- [ ] Alerting on key metrics
- [ ] Distributed tracing for microservices

## Common Performance Pitfalls

1. **No caching** - Repeatedly querying same data
2. **Missing indexes** - Full table scans
3. **N+1 queries** - Fetching related data in loops
4. **Synchronous processing** - Blocking on long tasks
5. **No connection pooling** - Creating new connections per request
6. **Unbounded queries** - No LIMIT on large tables
7. **No CDN** - Serving static assets from origin

## Resources

- **PostgreSQL Performance:** https://www.postgresql.org/docs/current/performance-tips.html
- **Redis Best Practices:** https://redis.io/docs/management/optimization/
- **Web Performance:** https://web.dev/performance/
- **Database Indexing:** https://use-the-index-luke.com/

# MongoDB Indexing and Performance (continued 2/2)

## Query Optimization

### Covered Queries
```javascript
// Query covered by index (no document fetch)
db.users.createIndex({ email: 1, name: 1 })

// Covered query (all fields in index)
db.users.find(
  { email: "user@example.com" },
  { email: 1, name: 1, _id: 0 }  // Must exclude _id
)

// Check with explain: stage should be "IXSCAN" with no "FETCH"
```

### Index Intersection
```javascript
// MongoDB can use multiple indexes
db.collection.createIndex({ a: 1 })
db.collection.createIndex({ b: 1 })

// Query may use both indexes
db.collection.find({ a: 1, b: 1 })

// Usually compound index is better
db.collection.createIndex({ a: 1, b: 1 })
```

### Index Hints
```javascript
// Force specific index
db.orders.find({ status: "active", city: "NYC" })
  .hint({ status: 1, createdAt: -1 })

// Force no index (for testing)
db.orders.find({ status: "active" }).hint({ $natural: 1 })
```

### ESR Rule (Equality, Sort, Range)
```javascript
// Optimal compound index order: Equality → Sort → Range

// Query
db.orders.find({
  status: "completed",        // Equality
  category: "electronics"     // Equality
}).sort({
  orderDate: -1               // Sort
}).limit(10)

// Optimal index
db.orders.createIndex({
  status: 1,      // Equality first
  category: 1,    // Equality
  orderDate: -1   // Sort last
})

// With range
db.orders.find({
  status: "completed",        // Equality
  total: { $gte: 100 }       // Range
}).sort({
  orderDate: -1               // Sort
})

// Optimal index
db.orders.createIndex({
  status: 1,      // Equality
  orderDate: -1,  // Sort
  total: 1        // Range last
})
```

## Performance Analysis

### explain() Modes
```javascript
// Query planner (default)
db.collection.find({ field: value }).explain()

// Execution stats
db.collection.find({ field: value }).explain("executionStats")

// All execution stats
db.collection.find({ field: value }).explain("allPlansExecution")
```

### Key Metrics
```javascript
// Good performance indicators:
// - executionTimeMillis < 100ms
// - totalDocsExamined ≈ nReturned (examine only what's needed)
// - stage: "IXSCAN" (using index)
// - totalKeysExamined ≈ nReturned (index selectivity)

// Bad indicators:
// - stage: "COLLSCAN" (full collection scan)
// - totalDocsExamined >> nReturned (scanning too many docs)
// - executionTimeMillis > 1000ms
```

### Index Selectivity
```javascript
// High selectivity = good (returns few documents)
// Low selectivity = bad (returns many documents)

// Check selectivity
db.collection.aggregate([
  { $group: { _id: "$status", count: { $sum: 1 } } }
])

// Good for indexing: email, userId, orderId
// Bad for indexing: gender, status (few unique values)
```

## Index Strategies

### Multi-Tenant Applications
```javascript
// Always filter by tenant first
db.data.createIndex({ tenantId: 1, createdAt: -1 })

// All queries include tenantId
db.data.find({ tenantId: "tenant1", createdAt: { $gte: date } })
```

### Time-Series Data
```javascript
// Index on timestamp descending (recent data accessed more)
db.events.createIndex({ timestamp: -1 })

// Compound with filter fields
db.events.createIndex({ userId: 1, timestamp: -1 })
```

### Lookup Optimization
```javascript
// Index foreign key fields
db.orders.createIndex({ customerId: 1 })
db.customers.createIndex({ _id: 1 })  // Default _id index

// Aggregation $lookup uses these indexes
```

## Best Practices

1. **Create indexes for frequent queries** - Analyze slow query logs
2. **Limit number of indexes** - Each index adds write overhead
3. **Use compound indexes** - More efficient than multiple single indexes
4. **Follow ESR rule** - Equality, Sort, Range order
5. **Use covered queries** - When possible, avoid document fetches
6. **Monitor index usage** - Drop unused indexes
```javascript
db.collection.aggregate([{ $indexStats: {} }])
```
7. **Partial indexes for filtered queries** - Reduce index size
8. **Consider index size** - Should fit in RAM
```javascript
db.collection.stats().indexSizes
```
9. **Background index creation** - Don't block operations (deprecated in 4.2+)
10. **Test with explain** - Verify query plan before production

## Common Pitfalls

1. **Over-indexing** - Too many indexes slow writes
2. **Unused indexes** - Waste space and write performance
3. **Regex without prefix** - `/pattern/` can't use index, `/^pattern/` can
4. **$ne, $nin queries** - Often scan entire collection
5. **$or with multiple branches** - May not use indexes efficiently
6. **Sort without index** - In-memory sort limited to 32MB
7. **Compound index order** - Wrong order makes index useless
8. **Case-sensitive queries** - Use collation for case-insensitive

## Monitoring

```javascript
// Current operations
db.currentOp()

// Slow queries (enable profiling)
db.setProfilingLevel(1, { slowms: 100 })
db.system.profile.find().sort({ ts: -1 }).limit(10)

// Index statistics
db.collection.aggregate([
  { $indexStats: {} },
  { $sort: { "accesses.ops": -1 } }
])

// Collection statistics
db.collection.stats()
```

## Index Size Calculation

```javascript
// Check index sizes
db.collection.stats().indexSizes

// Total index size
db.collection.totalIndexSize()

// Recommend: indexes fit in RAM
// Monitor: db.serverStatus().mem
```

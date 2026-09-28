# MongoDB Indexing and Performance

Index types, strategies, and performance optimization techniques for MongoDB.

## Index Fundamentals

Indexes let MongoDB scan fewer documents; without one, it runs a full collection scan (reads every document).

```javascript
// Check if query uses index
db.users.find({ email: "user@example.com" }).explain("executionStats")

// Key metrics:
// - executionTimeMillis: query duration
// - totalDocsExamined: documents scanned
// - nReturned: documents returned
// - stage: IXSCAN (index) vs COLLSCAN (full scan)
```

## Index Types

### Single Field Index
```javascript
// Create index on single field
db.users.createIndex({ email: 1 })  // 1: ascending, -1: descending

// Use case: queries filtering by email
db.users.find({ email: "user@example.com" })

// Drop index
db.users.dropIndex({ email: 1 })
db.users.dropIndex("email_1")  // By name
```

### Compound Index
```javascript
// Index on multiple fields (order matters!)
db.orders.createIndex({ status: 1, createdAt: -1 })

// Supports queries on:
// 1. { status: "..." }
// 2. { status: "...", createdAt: ... }
// Does NOT efficiently support: { createdAt: ... } alone

// Left-to-right prefix rule
db.orders.createIndex({ a: 1, b: 1, c: 1 })
// Supports: {a}, {a,b}, {a,b,c}
// Not: {b}, {c}, {b,c}
```

### Text Index (Full-Text Search)
```javascript
// Create text index
db.articles.createIndex({ title: "text", body: "text" })

// Only one text index per collection
db.articles.createIndex({
  title: "text",
  body: "text",
  tags: "text"
}, {
  weights: {
    title: 10,    // Title matches weighted higher
    body: 5,
    tags: 3
  }
})

// Search
db.articles.find({ $text: { $search: "mongodb database" } })

// Search with score
db.articles.find(
  { $text: { $search: "mongodb" } },
  { score: { $meta: "textScore" } }
).sort({ score: { $meta: "textScore" } })
```

### Geospatial Indexes
```javascript
// 2dsphere index (spherical geometry)
db.places.createIndex({ location: "2dsphere" })

// Document format
db.places.insertOne({
  name: "Coffee Shop",
  location: {
    type: "Point",
    coordinates: [-73.97, 40.77]  // [longitude, latitude]
  }
})

// Find nearby
db.places.find({
  location: {
    $near: {
      $geometry: { type: "Point", coordinates: [-73.97, 40.77] },
      $maxDistance: 5000  // meters
    }
  }
})

// Within polygon
db.places.find({
  location: {
    $geoWithin: {
      $geometry: {
        type: "Polygon",
        coordinates: [[
          [lon1, lat1], [lon2, lat2], [lon3, lat3], [lon1, lat1]
        ]]
      }
    }
  }
})
```

### Wildcard Index
```javascript
// Index all fields in subdocuments
db.products.createIndex({ "attributes.$**": 1 })

// Supports queries on any nested field
db.products.find({ "attributes.color": "red" })
db.products.find({ "attributes.size": "large" })

// Specific paths only
db.products.createIndex(
  { "$**": 1 },
  { wildcardProjection: { "attributes.color": 1, "attributes.size": 1 } }
)
```

### Hashed Index
```javascript
// Hashed index (for even distribution in sharding)
db.users.createIndex({ userId: "hashed" })

// Use case: shard key
sh.shardCollection("mydb.users", { userId: "hashed" })
```

### TTL Index (Auto-Expiration)
```javascript
// Delete documents after specified time
db.sessions.createIndex(
  { createdAt: 1 },
  { expireAfterSeconds: 3600 }  // 1 hour
)

// Documents automatically deleted after createdAt + 3600 seconds
// Background task runs every 60 seconds
```

### Partial Index
```javascript
// Index only documents matching filter
db.orders.createIndex(
  { customerId: 1 },
  { partialFilterExpression: { status: "active" } }
)

// Index only used when query includes filter
db.orders.find({ customerId: "123", status: "active" })  // Uses index
db.orders.find({ customerId: "123" })  // Does not use index
```

### Unique Index
```javascript
// Enforce uniqueness
db.users.createIndex({ email: 1 }, { unique: true })

// Compound unique index
db.users.createIndex({ firstName: 1, lastName: 1 }, { unique: true })

// Sparse unique index (null values not indexed)
db.users.createIndex({ email: 1 }, { unique: true, sparse: true })
```

### Sparse Index
```javascript
// Index only documents with field present
db.users.createIndex({ phoneNumber: 1 }, { sparse: true })

// Useful for optional fields
// Documents without phoneNumber not in index
```

## Index Management

### List Indexes
```javascript
// Show all indexes
db.collection.getIndexes()

// Index statistics
db.collection.aggregate([{ $indexStats: {} }])
```

### Create Index Options
```javascript
// Background index (doesn't block operations)
db.collection.createIndex({ field: 1 }, { background: true })

// Index name
db.collection.createIndex({ field: 1 }, { name: "custom_index_name" })

// Case-insensitive index (collation)
db.collection.createIndex(
  { name: 1 },
  { collation: { locale: "en", strength: 2 } }
)
```

### Hide/Unhide Index
```javascript
// Hide index (test before dropping)
db.collection.hideIndex("index_name")

// Check performance without index
// ...

// Unhide or drop
db.collection.unhideIndex("index_name")
db.collection.dropIndex("index_name")
```

### Rebuild Indexes
```javascript
// Rebuild all indexes (after data changes)
db.collection.reIndex()

// Useful after bulk deletions to reclaim space
```


---

Continued in [mongodb-indexing-cont.md](mongodb-indexing-cont.md)

# MongoDB Aggregation Pipeline (continued 2/2)

## Aggregation Operators

### Arithmetic Operators
```javascript
// Basic math
db.products.aggregate([
  { $project: {
    name: 1,
    profit: { $subtract: ["$price", "$cost"] },
    margin: { $multiply: [
      { $divide: [
        { $subtract: ["$price", "$cost"] },
        "$price"
      ]},
      100
    ]}
  }}
])

// Other operators: $add, $multiply, $divide, $mod, $abs, $ceil, $floor, $round
```

### String Operators
```javascript
// String manipulation
db.users.aggregate([
  { $project: {
    fullName: { $concat: ["$firstName", " ", "$lastName"] },
    email: { $toLower: "$email" },
    initials: { $concat: [
      { $substr: ["$firstName", 0, 1] },
      { $substr: ["$lastName", 0, 1] }
    ]}
  }}
])

// Other: $toUpper, $trim, $split, $substr, $regexMatch
```

### Date Operators
```javascript
// Date extraction
db.events.aggregate([
  { $project: {
    event: 1,
    year: { $year: "$timestamp" },
    month: { $month: "$timestamp" },
    day: { $dayOfMonth: "$timestamp" },
    hour: { $hour: "$timestamp" },
    dayOfWeek: { $dayOfWeek: "$timestamp" }
  }}
])

// Date math
db.events.aggregate([
  { $project: {
    event: 1,
    expiresAt: { $add: ["$createdAt", 1000 * 60 * 60 * 24 * 30] }, // +30 days
    ageInDays: { $divide: [
      { $subtract: [new Date(), "$createdAt"] },
      1000 * 60 * 60 * 24
    ]}
  }}
])
```

### Array Operators
```javascript
// Array operations
db.posts.aggregate([
  { $project: {
    title: 1,
    tagCount: { $size: "$tags" },
    firstTag: { $arrayElemAt: ["$tags", 0] },
    lastTag: { $arrayElemAt: ["$tags", -1] },
    hasMongoDBTag: { $in: ["mongodb", "$tags"] }
  }}
])

// Array filtering
db.posts.aggregate([
  { $project: {
    title: 1,
    activeTags: {
      $filter: {
        input: "$tags",
        as: "tag",
        cond: { $ne: ["$$tag.status", "deprecated"] }
      }
    }
  }}
])
```

### Conditional Operators
```javascript
// $cond (ternary)
db.products.aggregate([
  { $project: {
    name: 1,
    status: {
      $cond: {
        if: { $gte: ["$stock", 10] },
        then: "In Stock",
        else: "Low Stock"
      }
    }
  }}
])

// $switch (multiple conditions)
db.orders.aggregate([
  { $project: {
    status: 1,
    priority: {
      $switch: {
        branches: [
          { case: { $gte: ["$total", 1000] }, then: "High" },
          { case: { $gte: ["$total", 100] }, then: "Medium" }
        ],
        default: "Low"
      }
    }
  }}
])
```

## Advanced Patterns

### Time-Based Aggregation
```javascript
// Daily sales
db.orders.aggregate([
  { $match: { orderDate: { $gte: startDate } } },
  { $group: {
    _id: {
      year: { $year: "$orderDate" },
      month: { $month: "$orderDate" },
      day: { $dayOfMonth: "$orderDate" }
    },
    revenue: { $sum: "$total" },
    orderCount: { $sum: 1 }
  }},
  { $sort: { "_id.year": 1, "_id.month": 1, "_id.day": 1 } }
])
```

### Faceted Search
```javascript
// Multiple aggregations in one query
db.products.aggregate([
  { $match: { category: "electronics" } },
  { $facet: {
    priceRanges: [
      { $bucket: {
        groupBy: "$price",
        boundaries: [0, 100, 500, 1000, 5000],
        default: "5000+",
        output: { count: { $sum: 1 } }
      }}
    ],
    topBrands: [
      { $group: { _id: "$brand", count: { $sum: 1 } } },
      { $sort: { count: -1 } },
      { $limit: 5 }
    ],
    avgPrice: [
      { $group: { _id: null, avg: { $avg: "$price" } } }
    ]
  }}
])
```

### Window Functions
```javascript
// Running totals and moving averages
db.sales.aggregate([
  { $setWindowFields: {
    partitionBy: "$region",
    sortBy: { date: 1 },
    output: {
      runningTotal: {
        $sum: "$amount",
        window: { documents: ["unbounded", "current"] }
      },
      movingAvg: {
        $avg: "$amount",
        window: { documents: [-7, 0] }  // Last 7 days
      }
    }
  }}
])
```

### Text Search with Aggregation
```javascript
// Full-text search (requires text index)
db.articles.aggregate([
  { $match: { $text: { $search: "mongodb database" } } },
  { $addFields: { score: { $meta: "textScore" } } },
  { $sort: { score: -1 } },
  { $limit: 10 }
])
```

### Geospatial Aggregation
```javascript
// Find nearby locations
db.places.aggregate([
  { $geoNear: {
    near: { type: "Point", coordinates: [lon, lat] },
    distanceField: "distance",
    maxDistance: 5000,
    spherical: true
  }},
  { $limit: 10 }
])
```

## Performance Tips

1. **$match early** - Filter documents before other stages
2. **$project early** - Reduce document size
3. **Index usage** - $match and $sort can use indexes (only at start)
4. **$limit after $sort** - Reduce memory usage
5. **Avoid $lookup** - Prefer embedded documents when possible
6. **Use $facet sparingly** - Can be memory intensive
7. **allowDiskUse** - Enable for large datasets
```javascript
db.collection.aggregate(pipeline, { allowDiskUse: true })
```

## Best Practices

1. **Order stages efficiently** - $match → $project → $group → $sort → $limit
2. **Use $expr carefully** - Can prevent index usage
3. **Monitor memory** - Default limit: 100MB per stage
4. **Test with explain** - Analyze pipeline performance
```javascript
db.collection.explain("executionStats").aggregate(pipeline)
```
5. **Break complex pipelines** - Use $out/$merge for intermediate results
6. **Use $sample** - For random document selection
7. **Leverage $addFields** - Cleaner than $project for adding fields

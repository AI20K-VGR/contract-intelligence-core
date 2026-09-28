# MongoDB Aggregation Pipeline

Aggregation pipeline for complex data transformations, analytics, and multi-stage processing.

## Pipeline Concept

Aggregation processes documents through multiple stages. Each stage transforms documents and passes results to next stage.

```javascript
db.collection.aggregate([
  { /* Stage 1 */ },
  { /* Stage 2 */ },
  { /* Stage 3 */ }
])
```

## Core Pipeline Stages

### $match (Filter Documents)
```javascript
// Filter early in pipeline for efficiency
db.orders.aggregate([
  { $match: { status: "completed", total: { $gte: 100 } } },
  // Subsequent stages process only matched documents
])

// Multiple conditions
db.orders.aggregate([
  { $match: {
    $and: [
      { orderDate: { $gte: startDate } },
      { status: { $in: ["completed", "shipped"] } }
    ]
  }}
])
```

### $project (Reshape Documents)
```javascript
// Select and reshape fields
db.orders.aggregate([
  { $project: {
    orderNumber: 1,
    total: 1,
    customerName: "$customer.name",
    year: { $year: "$orderDate" },
    _id: 0  // Exclude _id
  }}
])

// Computed fields
db.orders.aggregate([
  { $project: {
    total: 1,
    tax: { $multiply: ["$total", 0.1] },
    grandTotal: { $add: ["$total", { $multiply: ["$total", 0.1] }] }
  }}
])
```

### $group (Aggregate Data)
```javascript
// Group and count
db.orders.aggregate([
  { $group: {
    _id: "$status",
    count: { $sum: 1 }
  }}
])

// Multiple aggregations
db.orders.aggregate([
  { $group: {
    _id: "$customerId",
    totalSpent: { $sum: "$total" },
    orderCount: { $sum: 1 },
    avgOrderValue: { $avg: "$total" },
    maxOrder: { $max: "$total" },
    minOrder: { $min: "$total" }
  }}
])

// Group by multiple fields
db.sales.aggregate([
  { $group: {
    _id: {
      year: { $year: "$date" },
      month: { $month: "$date" },
      product: "$productId"
    },
    revenue: { $sum: "$amount" }
  }}
])
```

### $sort (Order Results)
```javascript
// Sort by field
db.orders.aggregate([
  { $sort: { total: -1 } }  // -1: descending, 1: ascending
])

// Sort by multiple fields
db.orders.aggregate([
  { $sort: { status: 1, orderDate: -1 } }
])
```

### $limit / $skip (Pagination)
```javascript
// Limit results
db.orders.aggregate([
  { $sort: { orderDate: -1 } },
  { $limit: 10 }
])

// Pagination
const page = 2;
const pageSize = 20;
db.orders.aggregate([
  { $sort: { orderDate: -1 } },
  { $skip: (page - 1) * pageSize },
  { $limit: pageSize }
])
```

### $lookup (Join Collections)
```javascript
// Simple join
db.orders.aggregate([
  { $lookup: {
    from: "customers",
    localField: "customerId",
    foreignField: "_id",
    as: "customer"
  }},
  { $unwind: "$customer" }  // Convert array to object
])

// Pipeline join (more powerful)
db.orders.aggregate([
  { $lookup: {
    from: "products",
    let: { items: "$items" },
    pipeline: [
      { $match: { $expr: { $in: ["$_id", "$$items.productId"] } } },
      { $project: { name: 1, price: 1 } }
    ],
    as: "productDetails"
  }}
])
```

### $unwind (Deconstruct Arrays)
```javascript
// Unwind array field
db.orders.aggregate([
  { $unwind: "$items" }
])

// Preserve null/empty arrays
db.orders.aggregate([
  { $unwind: {
    path: "$items",
    preserveNullAndEmptyArrays: true
  }}
])

// Include array index
db.orders.aggregate([
  { $unwind: {
    path: "$items",
    includeArrayIndex: "itemIndex"
  }}
])
```

### $addFields (Add New Fields)
```javascript
// Add computed fields
db.orders.aggregate([
  { $addFields: {
    totalWithTax: { $multiply: ["$total", 1.1] },
    year: { $year: "$orderDate" }
  }}
])
```

### $replaceRoot (Replace Document Root)
```javascript
// Promote subdocument to root
db.orders.aggregate([
  { $replaceRoot: { newRoot: "$customer" } }
])

// Merge fields
db.orders.aggregate([
  { $replaceRoot: {
    newRoot: { $mergeObjects: ["$customer", { orderId: "$_id" }] }
  }}
])
```


---

Continued in [mongodb-aggregation-cont.md](mongodb-aggregation-cont.md)

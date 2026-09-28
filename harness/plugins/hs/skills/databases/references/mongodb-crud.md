# MongoDB CRUD Operations

CRUD operations (Create, Read, Update, Delete) in MongoDB with query operators and atomic updates.

## Create Operations

### insertOne
```javascript
// Insert single document
db.users.insertOne({
  name: "Alice",
  email: "alice@example.com",
  age: 30,
  createdAt: new Date()
})

// Returns: { acknowledged: true, insertedId: ObjectId("...") }
```

### insertMany
```javascript
// Insert multiple documents
db.users.insertMany([
  { name: "Bob", age: 25 },
  { name: "Charlie", age: 35 },
  { name: "Diana", age: 28 }
])

// With ordered: false (continue on error)
db.users.insertMany(docs, { ordered: false })
```

## Read Operations

### find
```javascript
// Find all documents
db.users.find()

// Find with filter
db.users.find({ age: { $gte: 18 } })

// Projection (select fields)
db.users.find({ status: "active" }, { name: 1, email: 1, _id: 0 })

// Cursor operations
db.users.find()
  .sort({ createdAt: -1 })
  .limit(10)
  .skip(20)
```

### findOne
```javascript
// Get single document
db.users.findOne({ email: "alice@example.com" })

// With projection
db.users.findOne({ _id: ObjectId("...") }, { name: 1, email: 1 })
```

### count/estimatedDocumentCount
```javascript
// Count matching documents
db.users.countDocuments({ status: "active" })

// Fast estimate (uses metadata)
db.users.estimatedDocumentCount()
```

### distinct
```javascript
// Get unique values
db.users.distinct("status")
db.users.distinct("city", { country: "USA" })
```

## Update Operations

### updateOne
```javascript
// Update first matching document
db.users.updateOne(
  { email: "alice@example.com" },
  { $set: { status: "verified" } }
)

// Upsert (insert if not exists)
db.users.updateOne(
  { email: "new@example.com" },
  { $set: { name: "New User" } },
  { upsert: true }
)
```

### updateMany
```javascript
// Update all matching documents
db.users.updateMany(
  { lastLogin: { $lt: cutoffDate } },
  { $set: { status: "inactive" } }
)

// Multiple updates
db.users.updateMany(
  { status: "pending" },
  {
    $set: { status: "active" },
    $currentDate: { updatedAt: true }
  }
)
```

### replaceOne
```javascript
// Replace entire document (except _id)
db.users.replaceOne(
  { _id: ObjectId("...") },
  { name: "Alice", email: "alice@example.com", age: 31 }
)
```

## Delete Operations

### deleteOne
```javascript
// Delete first matching document
db.users.deleteOne({ email: "alice@example.com" })
```

### deleteMany
```javascript
// Delete all matching documents
db.users.deleteMany({ status: "deleted" })

// Delete all documents in collection
db.users.deleteMany({})
```

## Query Operators

### Comparison Operators
```javascript
// $eq (equals)
db.users.find({ age: { $eq: 30 } })
db.users.find({ age: 30 })  // Implicit $eq

// $ne (not equals)
db.users.find({ status: { $ne: "deleted" } })

// $gt, $gte, $lt, $lte
db.users.find({ age: { $gt: 18, $lte: 65 } })

// $in (in array)
db.users.find({ status: { $in: ["active", "pending"] } })

// $nin (not in array)
db.users.find({ status: { $nin: ["deleted", "banned"] } })
```

### Logical Operators
```javascript
// $and (implicit for multiple conditions)
db.users.find({ age: { $gte: 18 }, status: "active" })

// $and (explicit)
db.users.find({
  $and: [
    { age: { $gte: 18 } },
    { status: "active" }
  ]
})

// $or
db.users.find({
  $or: [
    { status: "active" },
    { verified: true }
  ]
})

// $not
db.users.find({ age: { $not: { $lt: 18 } } })

// $nor (not any condition)
db.users.find({
  $nor: [
    { status: "deleted" },
    { status: "banned" }
  ]
})
```

### Element Operators
```javascript
// $exists
db.users.find({ phoneNumber: { $exists: true } })
db.users.find({ deletedAt: { $exists: false } })

// $type
db.users.find({ age: { $type: "int" } })
db.users.find({ age: { $type: ["int", "double"] } })
```

### Array Operators
```javascript
// $all (contains all elements)
db.posts.find({ tags: { $all: ["mongodb", "database"] } })

// $elemMatch (array element matches all conditions)
db.products.find({
  reviews: {
    $elemMatch: { rating: { $gte: 4 }, verified: true }
  }
})

// $size (array length)
db.posts.find({ tags: { $size: 3 } })
```

### String Operators
```javascript
// $regex (regular expression)
db.users.find({ name: { $regex: /^A/i } })
db.users.find({ email: { $regex: "@example\\.com$" } })

// Text search (requires text index)
db.articles.find({ $text: { $search: "mongodb database" } })
```


---

Continued in [mongodb-crud-cont.md](mongodb-crud-cont.md)

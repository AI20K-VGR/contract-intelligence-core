# MongoDB CRUD Operations (continued 2/2)

## Update Operators

### Field Update Operators
```javascript
// $set (set field value)
db.users.updateOne(
  { _id: userId },
  { $set: { status: "active", updatedAt: new Date() } }
)

// $unset (remove field)
db.users.updateOne(
  { _id: userId },
  { $unset: { tempField: "" } }
)

// $rename (rename field)
db.users.updateMany(
  {},
  { $rename: { "oldName": "newName" } }
)

// $currentDate (set to current date)
db.users.updateOne(
  { _id: userId },
  { $currentDate: { lastModified: true } }
)
```

### Numeric Update Operators
```javascript
// $inc (increment)
db.posts.updateOne(
  { _id: postId },
  { $inc: { views: 1, likes: 5 } }
)

// $mul (multiply)
db.products.updateOne(
  { _id: productId },
  { $mul: { price: 1.1 } }  // 10% increase
)

// $min (update if new value is less)
db.scores.updateOne(
  { _id: scoreId },
  { $min: { lowestScore: 50 } }
)

// $max (update if new value is greater)
db.scores.updateOne(
  { _id: scoreId },
  { $max: { highestScore: 100 } }
)
```

### Array Update Operators
```javascript
// $push (add to array)
db.posts.updateOne(
  { _id: postId },
  { $push: { comments: { author: "Alice", text: "Great!" } } }
)

// $push with $each (multiple elements)
db.posts.updateOne(
  { _id: postId },
  { $push: { tags: { $each: ["mongodb", "database"] } } }
)

// $addToSet (add if not exists)
db.users.updateOne(
  { _id: userId },
  { $addToSet: { interests: "coding" } }
)

// $pull (remove matching elements)
db.users.updateOne(
  { _id: userId },
  { $pull: { tags: "deprecated" } }
)

// $pop (remove first/last element)
db.users.updateOne(
  { _id: userId },
  { $pop: { notifications: -1 } }  // -1: first, 1: last
)

// $ (update first matching array element)
db.posts.updateOne(
  { _id: postId, "comments.author": "Alice" },
  { $set: { "comments.$.text": "Updated comment" } }
)

// $[] (update all array elements)
db.posts.updateOne(
  { _id: postId },
  { $set: { "comments.$[].verified": true } }
)

// $[<identifier>] (filtered positional)
db.posts.updateOne(
  { _id: postId },
  { $set: { "comments.$[elem].flagged": true } },
  { arrayFilters: [{ "elem.rating": { $lt: 2 } }] }
)
```

## Atomic Operations

### findAndModify / findOneAndUpdate
```javascript
// Find and update (returns old document by default)
db.users.findOneAndUpdate(
  { email: "alice@example.com" },
  { $set: { status: "active" } }
)

// Return new document
db.users.findOneAndUpdate(
  { email: "alice@example.com" },
  { $set: { status: "active" } },
  { returnNewDocument: true }
)

// Upsert and return new
db.counters.findOneAndUpdate(
  { _id: "sequence" },
  { $inc: { value: 1 } },
  { upsert: true, returnNewDocument: true }
)
```

### findOneAndReplace
```javascript
// Find and replace entire document
db.users.findOneAndReplace(
  { _id: ObjectId("...") },
  { name: "Alice", email: "alice@example.com" },
  { returnNewDocument: true }
)
```

### findOneAndDelete
```javascript
// Find and delete (returns deleted document)
const deletedUser = db.users.findOneAndDelete(
  { email: "alice@example.com" }
)
```

## Bulk Operations

```javascript
// Ordered bulk write (stops on first error)
db.users.bulkWrite([
  { insertOne: { document: { name: "Alice" } } },
  { updateOne: {
    filter: { name: "Bob" },
    update: { $set: { age: 25 } }
  }},
  { deleteOne: { filter: { name: "Charlie" } } }
])

// Unordered (continues on errors)
db.users.bulkWrite(operations, { ordered: false })
```

## Best Practices

1. **Use projection** to return only needed fields
2. **Create indexes** on frequently queried fields
3. **Use updateMany** carefully (can affect many documents)
4. **Use upsert** for "create or update" patterns
5. **Use atomic operators** ($inc, $push) for concurrent updates
6. **Avoid large arrays** in documents (embed vs reference)
7. **Use findAndModify** for atomic read-modify-write
8. **Batch operations** with insertMany/bulkWrite for efficiency

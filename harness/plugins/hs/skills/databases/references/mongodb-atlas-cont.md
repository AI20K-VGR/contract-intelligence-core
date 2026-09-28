# MongoDB Atlas Cloud Platform (continued 2/2)

## Atlas Vector Search (AI/ML)

### Create Vector Search Index
```javascript
// For AI similarity search (embeddings)
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,  // OpenAI embeddings
      "similarity": "cosine"
    }
  ]
}
```

### Vector Search Query
```javascript
// Search by similarity
db.products.aggregate([
  {
    $vectorSearch: {
      index: "vector_index",
      path: "embedding",
      queryVector: [0.123, 0.456, ...],  // 1536 dimensions
      numCandidates: 100,
      limit: 10
    }
  },
  {
    $project: {
      name: 1,
      description: 1,
      score: { $meta: "vectorSearchScore" }
    }
  }
])
```

## Data Federation

### Query Across Sources
```javascript
// Federated database instance
// Query data from:
// - Atlas clusters
// - AWS S3
// - HTTP endpoints

// Create virtual collection
{
  "databases": [{
    "name": "federated",
    "collections": [{
      "name": "sales",
      "dataSources": [{
        "storeName": "s3Store",
        "path": "/sales/*.json"
      }]
    }]
  }]
}

// Query like normal collection
use federated
db.sales.find({ region: "US" })
```

## Atlas Charts (Embedded Analytics)

### Create Dashboard
```javascript
// Atlas UI → Charts → New Dashboard
// Data source: Atlas cluster
// Chart types: bar, line, pie, scatter, etc.

// Embed in application
<iframe
  src="https://charts.mongodb.com/charts-project/embed/charts?id=..."
  width="800"
  height="600"
/>
```

## Atlas CLI

```bash
# Install
npm install -g mongodb-atlas-cli

# Login
atlas auth login

# List clusters
atlas clusters list

# Create cluster
atlas clusters create myCluster --provider AWS --region US_EAST_1 --tier M10

# Manage users
atlas dbusers create --username myuser --password mypass

# Backups
atlas backups snapshots list --clusterName myCluster
```

## Best Practices

1. **Use connection pooling** - Reuse connections
```javascript
const client = new MongoClient(uri, {
  maxPoolSize: 50,
  minPoolSize: 10
});
```

2. **Enable authentication** - Always use database users, not Atlas users

3. **Restrict network access** - IP whitelist or VPC peering

4. **Monitor regularly** - Set up alerts for key metrics

5. **Index optimization** - Use Performance Advisor recommendations

6. **Backup verification** - Regularly test restores

7. **Right-size clusters** - Start small, scale as needed

8. **Multi-region** - For global applications (M10+)

9. **Read preferences** - Use secondaries for read-heavy workloads
```javascript
const client = new MongoClient(uri, {
  readPreference: "secondaryPreferred"
});
```

10. **Connection string security** - Use environment variables
```javascript
const uri = process.env.MONGODB_URI;
```

## Troubleshooting

### Connection Issues
```javascript
// Check IP whitelist
// Verify credentials
// Test connection string

// Verbose logging
const client = new MongoClient(uri, {
  serverSelectionTimeoutMS: 5000,
  loggerLevel: "debug"
});
```

### Performance Issues
```javascript
// Check Performance Advisor
// Review slow query logs
// Analyze index usage
db.collection.aggregate([{ $indexStats: {} }])

// Check connection count
db.serverStatus().connections
```

### Common Errors
```javascript
// MongoNetworkError: IP not whitelisted
// → Add IP to Network Access

// Authentication failed: wrong credentials
// → Verify username/password in Database Access

// Timeout: connection string or network issue
// → Check connection string format, DNS resolution
```

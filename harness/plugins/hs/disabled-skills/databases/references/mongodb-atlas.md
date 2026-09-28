# MongoDB Atlas Cloud Platform

MongoDB Atlas: fully-managed cloud DB service - automated backups, monitoring, scaling.

## Quick Start

### Create Free Cluster
1. Sign up at mongodb.com/atlas
2. Create organization and project
3. Build cluster (M0 Free Tier)
   - Cloud provider: AWS/GCP/Azure
   - Region: closest to users
   - Cluster name
4. Create database user (username/password)
5. Whitelist IP address (or 0.0.0.0/0 for development)
6. Get connection string

### Connection String Format
```
mongodb+srv://username:password@cluster.mongodb.net/database?retryWrites=true&w=majority
```

### Connect
```javascript
// Node.js
const { MongoClient } = require("mongodb");
const uri = "mongodb+srv://...";
const client = new MongoClient(uri);

await client.connect();
const db = client.db("myDatabase");
```

```python
# Python
from pymongo import MongoClient
uri = "mongodb+srv://..."
client = MongoClient(uri)
db = client.myDatabase
```

## Cluster Tiers

### M0 (Free Tier)
- 512 MB storage
- Shared CPU/RAM
- Perfect for development/learning
- Limited to 100 connections
- No backups

### M10+ (Dedicated Clusters)
- Dedicated resources
- 2GB - 4TB+ storage
- Automated backups
- Advanced monitoring
- Performance Advisor
- Multi-region support
- VPC peering

### Serverless
- Pay per operation
- Auto-scales to zero
- Good for sporadic workloads
- 1GB+ storage
- Limited features (no full-text search)

## Database Configuration

### Create Database
```javascript
// Via Atlas UI: Database → Add Database
// Via shell
use myNewDatabase
db.createCollection("myCollection")

// Via driver
const db = client.db("myNewDatabase");
await db.createCollection("myCollection");
```

### Schema Validation
```javascript
// Set validation rules in Atlas UI or via shell
db.createCollection("users", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["email", "name"],
      properties: {
        email: { bsonType: "string", pattern: "^.+@.+$" },
        age: { bsonType: "int", minimum: 0 }
      }
    }
  }
})
```

## Security

### Network Access
```javascript
// IP Whitelist (Atlas UI → Network Access)
// - Add IP Address: specific IPs
// - 0.0.0.0/0: allow from anywhere (dev only)
// - VPC Peering: private connection

// Connection string includes options
mongodb+srv://cluster.mongodb.net/?retryWrites=true&w=majority&ssl=true
```

### Database Users
```javascript
// Create via Atlas UI → Database Access
// - Username/password authentication
// - AWS IAM authentication
// - X.509 certificates

// Roles:
// - atlasAdmin: full access
// - readWriteAnyDatabase: read/write all databases
// - readAnyDatabase: read-only all databases
// - read/readWrite: database-specific
```

### Encryption
```javascript
// Encryption at rest (automatic on M10+)
// Encryption in transit (TLS/SSL, always enabled)

// Client-Side Field Level Encryption (CSFLE)
const autoEncryptionOpts = {
  keyVaultNamespace: "encryption.__keyVault",
  kmsProviders: {
    aws: {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID,
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
    }
  }
};

const client = new MongoClient(uri, { autoEncryption: autoEncryptionOpts });
```

## Backups and Snapshots

### Cloud Backups (M10+)
```javascript
// Automatic continuous backups
// - Snapshots every 6-24 hours
// - Oplog for point-in-time recovery
// - Retention: 2+ days configurable

// Restore via Atlas UI:
// 1. Clusters → cluster name → Backup tab
// 2. Select snapshot or point in time
// 3. Download or restore to cluster
```

### Manual Backups
```bash
# Export using mongodump
mongodump --uri="mongodb+srv://user:pass@cluster.mongodb.net/mydb" --out=/backup

# Restore using mongorestore
mongorestore --uri="mongodb+srv://..." /backup/mydb
```

## Monitoring and Alerts

### Metrics Dashboard
```javascript
// Atlas UI → Metrics
// Key metrics:
// - Operations per second
// - Query execution times
// - Connections
// - Network I/O
// - Disk usage
// - CPU utilization

// Real-time Performance panel
// - Current operations
// - Slow queries
// - Index suggestions
```

### Alerts
```javascript
// Configure via Atlas UI → Alerts
// Alert types:
// - High connections (> threshold)
// - High CPU usage (> 80%)
// - Disk usage (> 90%)
// - Replication lag
// - Backup failures

// Notification channels:
// - Email
// - SMS
// - Slack
// - PagerDuty
// - Webhook
```

### Performance Advisor
```javascript
// Automatic index recommendations
// Atlas UI → Performance Advisor

// Analyzes:
// - Slow queries
// - Missing indexes
// - Redundant indexes
// - Index usage statistics

// Provides:
// - Index creation commands
// - Expected performance improvement
// - Schema design suggestions
```

## Atlas Search (Full-Text Search)

### Create Search Index
```javascript
// Atlas UI → Search → Create Index

// JSON definition
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "title": {
        "type": "string",
        "analyzer": "lucene.standard"
      },
      "description": {
        "type": "string",
        "analyzer": "lucene.english"
      },
      "tags": {
        "type": "string"
      }
    }
  }
}
```

### Search Queries
```javascript
// Aggregation pipeline with $search
db.articles.aggregate([
  {
    $search: {
      text: {
        query: "mongodb database tutorial",
        path: ["title", "description"],
        fuzzy: { maxEdits: 1 }
      }
    }
  },
  { $limit: 10 },
  {
    $project: {
      title: 1,
      description: 1,
      score: { $meta: "searchScore" }
    }
  }
])

// Autocomplete
db.articles.aggregate([
  {
    $search: {
      autocomplete: {
        query: "mong",
        path: "title",
        tokenOrder: "sequential"
      }
    }
  }
])
```


---

Continued in [mongodb-atlas-cont.md](mongodb-atlas-cont.md)

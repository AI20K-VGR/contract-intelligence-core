# PostgreSQL Performance Optimization

Query optimization, indexing strategies, EXPLAIN analysis, and performance tuning for PostgreSQL.

## EXPLAIN Command

### Basic EXPLAIN
```sql
-- Show query plan
EXPLAIN SELECT * FROM users WHERE id = 1;

-- Output shows:
-- - Execution plan nodes
-- - Estimated costs
-- - Estimated rows
```

### EXPLAIN ANALYZE
```sql
-- Execute query and show actual performance
EXPLAIN ANALYZE SELECT * FROM users WHERE age > 18;

-- Shows:
-- - Actual execution time
-- - Actual rows returned
-- - Planning time
-- - Execution time
```

### EXPLAIN Options
```sql
-- Verbose output
EXPLAIN (VERBOSE) SELECT * FROM users;

-- Show buffer usage
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM users WHERE active = true;

-- JSON format
EXPLAIN (FORMAT JSON, ANALYZE) SELECT * FROM users;

-- All options
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, TIMING, COSTS)
SELECT * FROM users WHERE id = 1;
```

## Understanding Query Plans

### Scan Methods

#### Sequential Scan
```sql
-- Full table scan (reads all rows)
EXPLAIN SELECT * FROM users WHERE name = 'Alice';

-- Output: Seq Scan on users
-- Indicates: no suitable index or small table
```

#### Index Scan
```sql
-- Uses index to find rows
EXPLAIN SELECT * FROM users WHERE id = 1;

-- Output: Index Scan using users_pkey on users
-- Best for: selective queries, small result sets
```

#### Index Only Scan
```sql
-- Query covered by index (no table access)
CREATE INDEX idx_users_email_name ON users(email, name);
EXPLAIN SELECT email, name FROM users WHERE email = 'alice@example.com';

-- Output: Index Only Scan using idx_users_email_name
-- Best performance: no heap fetch needed
```

#### Bitmap Scan
```sql
-- Combines multiple indexes or handles large result sets
EXPLAIN SELECT * FROM users WHERE age > 18 AND status = 'active';

-- Output:
-- Bitmap Heap Scan on users
--   Recheck Cond: ...
--   -> Bitmap Index Scan on idx_age

-- Good for: moderate selectivity
```

### Join Methods

#### Nested Loop
```sql
-- For each row in outer table, scan inner table
EXPLAIN SELECT * FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE c.id = 1;

-- Output: Nested Loop
-- Best for: small outer table, indexed inner table
```

#### Hash Join
```sql
-- Build hash table from smaller table
EXPLAIN SELECT * FROM orders o
JOIN customers c ON o.customer_id = c.id;

-- Output: Hash Join
-- Best for: large tables, equality conditions
```

#### Merge Join
```sql
-- Both inputs sorted on join key
EXPLAIN SELECT * FROM orders o
JOIN customers c ON o.customer_id = c.id
ORDER BY o.customer_id;

-- Output: Merge Join
-- Best for: pre-sorted data, large sorted inputs
```

## Indexing Strategies

### B-tree Index (Default)
```sql
-- General purpose index
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_orders_date ON orders(order_date);

-- Supports: =, <, <=, >, >=, BETWEEN, IN, IS NULL
-- Supports: ORDER BY, MIN/MAX
```

### Composite Index
```sql
-- Multiple columns (order matters!)
CREATE INDEX idx_users_status_created ON users(status, created_at);

-- Supports queries on:
-- - status
-- - status, created_at
-- Does NOT support: created_at alone

-- Column order: most selective first
-- Exception: match query WHERE/ORDER BY patterns
```

### Partial Index
```sql
-- Index subset of rows
CREATE INDEX idx_active_users ON users(email)
WHERE status = 'active';

-- Smaller index, faster queries with matching WHERE clause
-- Query must include WHERE status = 'active' to use index
```

### Expression Index
```sql
-- Index on computed value
CREATE INDEX idx_users_lower_email ON users(LOWER(email));

-- Query must use same expression
SELECT * FROM users WHERE LOWER(email) = 'alice@example.com';
```

### GIN Index (Generalized Inverted Index)
```sql
-- For array, JSONB, full-text search
CREATE INDEX idx_products_tags ON products USING GIN(tags);
CREATE INDEX idx_documents_data ON documents USING GIN(data);

-- Array queries
SELECT * FROM products WHERE tags @> ARRAY['featured'];

-- JSONB queries
SELECT * FROM documents WHERE data @> '{"status": "active"}';
```

### GiST Index (Generalized Search Tree)
```sql
-- For geometric data, range types, full-text
CREATE INDEX idx_locations_geom ON locations USING GiST(geom);

-- Geometric queries
SELECT * FROM locations WHERE geom && ST_MakeEnvelope(...);
```

### Hash Index
```sql
-- Equality comparisons only
CREATE INDEX idx_users_hash_email ON users USING HASH(email);

-- Only supports: =
-- Rarely used (B-tree usually better)
```

### BRIN Index (Block Range Index)
```sql
-- For very large tables with natural clustering
CREATE INDEX idx_logs_brin_created ON logs USING BRIN(created_at);

-- Tiny index size, good for append-only data
-- Best for: time-series, logging, large tables
```


---

Continued in [postgresql-performance-cont.md](postgresql-performance-cont.md)

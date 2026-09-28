# PostgreSQL Performance Optimization (continued 2/3)

## Query Optimization Techniques

### Avoid SELECT *
```sql
-- Bad
SELECT * FROM users WHERE id = 1;

-- Good (only needed columns)
SELECT id, name, email FROM users WHERE id = 1;
```

### Use LIMIT
```sql
-- Limit result set
SELECT * FROM users ORDER BY created_at DESC LIMIT 10;

-- PostgreSQL can stop early with LIMIT
```

### Index for ORDER BY
```sql
-- Create index matching sort order
CREATE INDEX idx_users_created_desc ON users(created_at DESC);

-- Query uses index for sorting
SELECT * FROM users ORDER BY created_at DESC LIMIT 10;
```

### Covering Index
```sql
-- Include all queried columns in index
CREATE INDEX idx_users_email_name_status ON users(email, name, status);

-- Query covered by index (no table access)
SELECT name, status FROM users WHERE email = 'alice@example.com';
```

### EXISTS vs IN
```sql
-- Prefer EXISTS for large subqueries
-- Bad
SELECT * FROM customers
WHERE id IN (SELECT customer_id FROM orders WHERE total > 1000);

-- Good
SELECT * FROM customers c
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.total > 1000);
```

### JOIN Order
```sql
-- Filter before joining
-- Bad
SELECT * FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status = 'completed' AND c.country = 'USA';

-- Good (filter in subquery)
SELECT * FROM (
  SELECT * FROM orders WHERE status = 'completed'
) o
JOIN (
  SELECT * FROM customers WHERE country = 'USA'
) c ON o.customer_id = c.id;

-- Or use CTE
WITH filtered_orders AS (
  SELECT * FROM orders WHERE status = 'completed'
),
filtered_customers AS (
  SELECT * FROM customers WHERE country = 'USA'
)
SELECT * FROM filtered_orders o
JOIN filtered_customers c ON o.customer_id = c.id;
```

### Avoid Functions in WHERE
```sql
-- Bad (index not used)
SELECT * FROM users WHERE LOWER(email) = 'alice@example.com';

-- Good (create expression index)
CREATE INDEX idx_users_lower_email ON users(LOWER(email));
-- Then query uses index

-- Or store lowercase separately
ALTER TABLE users ADD COLUMN email_lower TEXT;
UPDATE users SET email_lower = LOWER(email);
CREATE INDEX idx_users_email_lower ON users(email_lower);
```

## Statistics and ANALYZE

### Update Statistics
```sql
-- Analyze table (update statistics)
ANALYZE users;

-- Analyze specific columns
ANALYZE users(email, status);

-- Analyze all tables
ANALYZE;

-- Auto-analyze (configured in postgresql.conf)
autovacuum_analyze_threshold = 50
autovacuum_analyze_scale_factor = 0.1
```

### Check Statistics
```sql
-- Last analyze time
SELECT schemaname, tablename, last_analyze, last_autoanalyze
FROM pg_stat_user_tables;

-- Statistics targets (adjust for important columns)
ALTER TABLE users ALTER COLUMN email SET STATISTICS 1000;
```

## VACUUM and Maintenance

### VACUUM
```sql
-- Reclaim storage, update statistics
VACUUM users;

-- Verbose output
VACUUM VERBOSE users;

-- Full vacuum (rewrites table, locks table)
VACUUM FULL users;

-- Analyze after vacuum
VACUUM ANALYZE users;
```

### Auto-Vacuum
```sql
-- Check autovacuum status
SELECT schemaname, tablename, last_vacuum, last_autovacuum
FROM pg_stat_user_tables;

-- Configure in postgresql.conf
autovacuum = on
autovacuum_vacuum_threshold = 50
autovacuum_vacuum_scale_factor = 0.2
```

### REINDEX
```sql
-- Rebuild index
REINDEX INDEX idx_users_email;

-- Rebuild all indexes on table
REINDEX TABLE users;

-- Rebuild all indexes in schema
REINDEX SCHEMA public;
```

## Monitoring Queries

### Active Queries
```sql
-- Current queries
SELECT pid, usename, state, query, query_start
FROM pg_stat_activity
WHERE state != 'idle';

-- Long-running queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state != 'idle' AND now() - query_start > interval '5 minutes'
ORDER BY duration DESC;
```

### Slow Query Log
```sql
-- Enable slow query logging (postgresql.conf)
log_min_duration_statement = 100  -- milliseconds

-- Or per session
SET log_min_duration_statement = 100;

-- Logs appear in PostgreSQL log files
```

### pg_stat_statements Extension
```sql
-- Enable extension
CREATE EXTENSION pg_stat_statements;

-- View query statistics
SELECT query, calls, total_exec_time, mean_exec_time, rows
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Reset statistics
SELECT pg_stat_statements_reset();
```

## Index Usage Analysis

### Check Index Usage
```sql
-- Index usage statistics
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan;

-- Unused indexes (idx_scan = 0)
SELECT schemaname, tablename, indexname
FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND indexname NOT LIKE '%_pkey';
```

### Index Size
```sql
-- Index sizes
SELECT schemaname, tablename, indexname,
  pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
```

### Missing Indexes
```sql
-- Tables with sequential scans
SELECT schemaname, tablename, seq_scan, seq_tup_read
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC;

-- Consider adding indexes to high seq_scan tables
```

## Configuration Tuning

### Memory Settings (postgresql.conf)
```conf
# Shared buffers (25% of RAM)
shared_buffers = 4GB

# Work memory (per operation)
work_mem = 64MB

# Maintenance work memory (VACUUM, CREATE INDEX)
maintenance_work_mem = 512MB

# Effective cache size (estimate of OS cache)
effective_cache_size = 12GB
```

### Query Planner Settings
```conf
# Random page cost (lower for SSD)
random_page_cost = 1.1

# Effective IO concurrency (number of concurrent disk operations)
effective_io_concurrency = 200

# Cost of parallel query startup
parallel_setup_cost = 1000
parallel_tuple_cost = 0.1
```

### Connection Settings
```conf
# Max connections
max_connections = 100

# Connection pooling recommended (pgBouncer)
```


---

Continued in [postgresql-performance-cont2.md](postgresql-performance-cont2.md)

# PostgreSQL psql CLI (continued 2/2)

## Configuration

### ~/.psqlrc
```bash
# Auto-loaded on psql startup
\set QUIET ON

-- Prompt customization
\set PROMPT1 '%n@%m:%>/%/%R%# '

-- Output settings
\pset null '[NULL]'
\pset border 2
\pset linestyle unicode
\pset expanded auto

-- Timing
\timing ON

-- Pager
\pset pager always

-- History
\set HISTSIZE 10000

-- Custom shortcuts
\set active_users 'SELECT * FROM users WHERE status = ''active'';'
\set dbsize 'SELECT pg_size_pretty(pg_database_size(current_database()));'

\set QUIET OFF
```

### Useful Aliases
```bash
# Add to ~/.psqlrc
\set locks 'SELECT pid, usename, pg_blocking_pids(pid) as blocked_by, query FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid)) > 0;'

\set activity 'SELECT pid, usename, state, query FROM pg_stat_activity WHERE state != ''idle'';'

\set table_sizes 'SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||''.''||tablename)) FROM pg_tables ORDER BY pg_total_relation_size(schemaname||''.''||tablename) DESC;'

\set index_usage 'SELECT schemaname, tablename, indexname, idx_scan FROM pg_stat_user_indexes ORDER BY idx_scan;'

# Usage: :locks, :activity, :table_sizes
```

## Transactions

```sql
-- Begin transaction
BEGIN;

-- Or
START TRANSACTION;

-- Savepoint
SAVEPOINT sp1;

-- Rollback to savepoint
ROLLBACK TO sp1;

-- Commit
COMMIT;

-- Rollback
ROLLBACK;
```

## Performance Analysis

### EXPLAIN
```sql
-- Show query plan
EXPLAIN SELECT * FROM users WHERE id = 1;

-- With execution
EXPLAIN ANALYZE SELECT * FROM users WHERE age > 18;

-- Verbose
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT * FROM users WHERE active = true;
```

### Current Activity
```sql
-- Active queries
SELECT pid, usename, state, query
FROM pg_stat_activity;

-- Long-running queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;

-- Blocking queries
SELECT blocked.pid, blocking.pid AS blocking_pid,
       blocked.query AS blocked_query,
       blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
  ON blocking.pid = ANY(pg_blocking_pids(blocked.pid));
```

### Statistics
```sql
-- Database size
SELECT pg_size_pretty(pg_database_size(current_database()));

-- Table sizes
SELECT schemaname, tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan;
```

## User Management

```sql
-- Create user
CREATE USER appuser WITH PASSWORD 'secure_password';

-- Create superuser
CREATE USER admin WITH PASSWORD 'password' SUPERUSER;

-- Alter user
ALTER USER appuser WITH PASSWORD 'new_password';

-- Grant permissions
GRANT CONNECT ON DATABASE mydb TO appuser;
GRANT USAGE ON SCHEMA public TO appuser;
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO appuser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO appuser;

-- Default privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO appuser;

-- View permissions
\dp users

-- Drop user
DROP USER appuser;
```

## Backup Patterns

```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
pg_dump -Fc mydb > /backups/mydb_$DATE.dump

# Restore latest
pg_restore -d mydb /backups/mydb_latest.dump

# Backup all databases
pg_dumpall > /backups/all_databases.sql

# Backup specific schema
pg_dump -n public mydb > public_schema.sql
```

## Troubleshooting

### Connection Issues
```bash
# Test connection
psql -h hostname -U username -d postgres -c "SELECT 1;"

# Check pg_hba.conf
# /var/lib/postgresql/data/pg_hba.conf

# Verbose connection
psql -h hostname -d mydb --echo-all
```

### Performance Issues
```sql
-- Enable slow query logging
ALTER DATABASE mydb SET log_min_duration_statement = 100;

-- Check cache hit ratio
SELECT
  sum(heap_blks_read) as heap_read,
  sum(heap_blks_hit) as heap_hit,
  sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) AS ratio
FROM pg_statio_user_tables;

-- Find slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

## Best Practices

1. **Use .pgpass** for credential management
2. **Set ON_ERROR_STOP** in scripts
3. **Use transactions** for multi-statement changes
4. **Test with EXPLAIN** before running expensive queries
5. **Use \timing** to measure query performance
6. **Configure ~/.psqlrc** for productivity
7. **Use variables** for dynamic queries
8. **Log sessions** with -L for auditing
9. **Use \copy** instead of COPY for client operations
10. **Regular backups** with pg_dump

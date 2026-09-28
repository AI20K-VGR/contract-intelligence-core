# PostgreSQL Administration (continued 2/3)

## Replication

### Streaming Replication (Primary-Replica)

#### Primary Setup
```sql
-- Create replication user
CREATE USER replicator WITH REPLICATION PASSWORD 'replica_pass';

-- Configure postgresql.conf
wal_level = replica
max_wal_senders = 3
wal_keep_size = 64MB

-- Configure pg_hba.conf
host replication replicator replica_ip/32 md5
```

#### Replica Setup
```bash
# Stop replica PostgreSQL
systemctl stop postgresql

# Remove data directory
rm -rf /var/lib/postgresql/data/*

# Clone from primary
pg_basebackup -h primary_host -D /var/lib/postgresql/data -U replicator -P -R

# Start replica
systemctl start postgresql

# Check replication status
SELECT * FROM pg_stat_replication;  -- On primary
```

### Logical Replication

#### Publisher (Primary)
```sql
-- Create publication
CREATE PUBLICATION my_publication FOR ALL TABLES;

-- Or specific tables
CREATE PUBLICATION my_publication FOR TABLE users, orders;

-- Check publications
\dRp
SELECT * FROM pg_publication;
```

#### Subscriber (Replica)
```sql
-- Create subscription
CREATE SUBSCRIPTION my_subscription
CONNECTION 'host=primary_host dbname=mydb user=replicator password=replica_pass'
PUBLICATION my_publication;

-- Check subscriptions
\dRs
SELECT * FROM pg_subscription;

-- Monitor replication
SELECT * FROM pg_stat_subscription;
```

## Monitoring

### Database Size
```sql
-- Database size
SELECT pg_size_pretty(pg_database_size('mydb'));

-- Table sizes
SELECT schemaname, tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Index sizes
SELECT schemaname, tablename, indexname,
  pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
```

### Connections
```sql
-- Current connections
SELECT count(*) FROM pg_stat_activity;

-- Connections by database
SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;

-- Connection limit
SHOW max_connections;

-- Kill connection
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = 12345;
```

### Activity
```sql
-- Active queries
SELECT pid, usename, state, query, query_start
FROM pg_stat_activity
WHERE state != 'idle';

-- Long-running queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;

-- Blocking queries
SELECT blocked.pid AS blocked_pid,
       blocked.query AS blocked_query,
       blocking.pid AS blocking_pid,
       blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
  ON blocking.pid = ANY(pg_blocking_pids(blocked.pid));
```

### Cache Hit Ratio
```sql
-- Should be > 0.99 for good performance
SELECT
  sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) AS cache_hit_ratio
FROM pg_statio_user_tables;
```

### Table Bloat
```sql
-- Check for table bloat (requires pgstattuple extension)
CREATE EXTENSION pgstattuple;

SELECT schemaname, tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
  pgstattuple(schemaname||'.'||tablename) AS stats
FROM pg_tables
WHERE schemaname = 'public';
```

## Maintenance

### VACUUM
```sql
-- Reclaim storage
VACUUM users;

-- Verbose
VACUUM VERBOSE users;

-- Full (locks table, rewrites)
VACUUM FULL users;

-- With analyze
VACUUM ANALYZE users;

-- All tables
VACUUM;
```

### Auto-Vacuum
```sql
-- Check last vacuum
SELECT schemaname, tablename, last_vacuum, last_autovacuum
FROM pg_stat_user_tables;

-- Configure postgresql.conf
autovacuum = on
autovacuum_vacuum_threshold = 50
autovacuum_vacuum_scale_factor = 0.2
autovacuum_analyze_threshold = 50
autovacuum_analyze_scale_factor = 0.1
```

### REINDEX
```sql
-- Rebuild index
REINDEX INDEX idx_users_email;

-- Rebuild all indexes on table
REINDEX TABLE users;

-- Rebuild database indexes
REINDEX DATABASE mydb;

-- Concurrently (doesn't lock)
REINDEX INDEX CONCURRENTLY idx_users_email;
```

### ANALYZE
```sql
-- Update statistics
ANALYZE users;

-- Specific columns
ANALYZE users(email, status);

-- All tables
ANALYZE;

-- Verbose
ANALYZE VERBOSE users;
```

## Configuration

### postgresql.conf Location
```sql
SHOW config_file;
```

### Key Settings
```conf
# Memory
shared_buffers = 4GB                 # 25% of RAM
work_mem = 64MB                      # Per operation
maintenance_work_mem = 512MB         # VACUUM, CREATE INDEX
effective_cache_size = 12GB          # OS cache estimate

# Query Planner
random_page_cost = 1.1               # Lower for SSD
effective_io_concurrency = 200       # Concurrent disk ops

# Connections
max_connections = 100
superuser_reserved_connections = 3

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d.log'
log_rotation_age = 1d
log_min_duration_statement = 100     # Log slow queries

# Replication
wal_level = replica
max_wal_senders = 3
wal_keep_size = 64MB

# Autovacuum
autovacuum = on
autovacuum_vacuum_scale_factor = 0.2
autovacuum_analyze_scale_factor = 0.1
```

### Reload Configuration
```sql
-- Reload config without restart
SELECT pg_reload_conf();

-- Or from shell
pg_ctl reload
```


---

Continued in [postgresql-administration-cont2.md](postgresql-administration-cont2.md)

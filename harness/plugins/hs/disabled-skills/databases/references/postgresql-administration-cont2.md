# PostgreSQL Administration (continued 3/3)

## Security

### SSL/TLS
```conf
# postgresql.conf
ssl = on
ssl_cert_file = '/path/to/server.crt'
ssl_key_file = '/path/to/server.key'
ssl_ca_file = '/path/to/ca.crt'
```

### pg_hba.conf (Host-Based Authentication)
```conf
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Local connections
local   all             postgres                                peer
local   all             all                                     md5

# Remote connections
host    all             all             0.0.0.0/0               md5
host    all             all             ::0/0                   md5

# Replication
host    replication     replicator      replica_ip/32           md5

# SSL required
hostssl all             all             0.0.0.0/0               md5
```

### Row Level Security
```sql
-- Enable RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Create policy
CREATE POLICY user_policy ON users
  USING (user_id = current_user_id());

-- Drop policy
DROP POLICY user_policy ON users;

-- View policies
\d+ users
```

## Best Practices

1. **Backups**
   - Daily automated backups
   - Test restores regularly
   - Store backups off-site
   - Use pg_dump custom format for flexibility

2. **Monitoring**
   - Monitor connections, queries, cache hit ratio
   - Set up alerts for critical metrics
   - Log slow queries
   - Use pg_stat_statements

3. **Security**
   - Use strong passwords
   - Restrict network access (pg_hba.conf)
   - Enable SSL/TLS
   - Regular security updates
   - Principle of least privilege

4. **Maintenance**
   - Regular VACUUM and ANALYZE
   - Monitor autovacuum
   - REINDEX periodically
   - Check for table bloat

5. **Configuration**
   - Tune for workload
   - Use connection pooling (pgBouncer)
   - Monitor and adjust memory settings
   - Keep PostgreSQL updated

6. **Replication**
   - At least one replica for HA
   - Monitor replication lag
   - Test failover procedures
   - Use logical replication for selective replication

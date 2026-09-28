# PostgreSQL Administration

User management, backups, replication, maintenance, and production database administration.

## User and Role Management

### Create Users
```sql
-- Create user with password
CREATE USER appuser WITH PASSWORD 'secure_password';

-- Create superuser
CREATE USER admin WITH SUPERUSER PASSWORD 'admin_password';

-- Create role without login
CREATE ROLE readonly;

-- Create user with attributes
CREATE USER developer WITH
  PASSWORD 'dev_pass'
  CREATEDB
  VALID UNTIL '2025-12-31';
```

### Alter Users
```sql
-- Change password
ALTER USER appuser WITH PASSWORD 'new_password';

-- Add attributes
ALTER USER appuser WITH CREATEDB CREATEROLE;

-- Remove attributes
ALTER USER appuser WITH NOSUPERUSER;

-- Rename user
ALTER USER oldname RENAME TO newname;

-- Set connection limit
ALTER USER appuser CONNECTION LIMIT 10;
```

### Roles and Inheritance
```sql
-- Create role hierarchy
CREATE ROLE readonly;
CREATE ROLE readwrite;

-- Grant role to user
GRANT readonly TO appuser;
GRANT readwrite TO developer;

-- Revoke role
REVOKE readonly FROM appuser;

-- Role membership
\du
```

### Permissions

#### Database Level
```sql
-- Grant database access
GRANT CONNECT ON DATABASE mydb TO appuser;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO appuser;

-- Revoke access
REVOKE CONNECT ON DATABASE mydb FROM appuser;
```

#### Table Level
```sql
-- Grant table permissions
GRANT SELECT ON users TO appuser;
GRANT SELECT, INSERT, UPDATE ON orders TO appuser;
GRANT ALL PRIVILEGES ON products TO appuser;

-- Grant on all tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;

-- Revoke permissions
REVOKE INSERT ON users FROM appuser;
```

#### Column Level
```sql
-- Grant specific columns
GRANT SELECT (id, name, email) ON users TO appuser;
GRANT UPDATE (status) ON orders TO appuser;
```

#### Sequence Permissions
```sql
-- Grant sequence usage (for SERIAL/auto-increment)
GRANT USAGE, SELECT ON SEQUENCE users_id_seq TO appuser;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO appuser;
```

#### Function Permissions
```sql
-- Grant execute on function
GRANT EXECUTE ON FUNCTION get_user(integer) TO appuser;
```

### Default Privileges
```sql
-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO readwrite;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE ON SEQUENCES TO readwrite;
```

### View Permissions
```sql
-- Show table permissions
\dp users

-- Show role memberships
\du

-- Query permissions
SELECT grantee, privilege_type
FROM information_schema.role_table_grants
WHERE table_name = 'users';
```

## Backup and Restore

### pg_dump (Logical Backup)
```bash
# Dump database to SQL file
pg_dump mydb > mydb.sql

# Custom format (compressed, allows selective restore)
pg_dump -Fc mydb > mydb.dump

# Directory format (parallel dump)
pg_dump -Fd mydb -j 4 -f mydb_dir

# Specific table
pg_dump -t users mydb > users.sql

# Multiple tables
pg_dump -t users -t orders mydb > tables.sql

# Schema only
pg_dump -s mydb > schema.sql

# Data only
pg_dump -a mydb > data.sql

# Exclude table
pg_dump --exclude-table=logs mydb > mydb.sql

# With compression
pg_dump -Fc -Z 9 mydb > mydb.dump
```

### pg_dumpall (All Databases)
```bash
# Dump all databases
pg_dumpall > all_databases.sql

# Only globals (roles, tablespaces)
pg_dumpall --globals-only > globals.sql
```

### pg_restore
```bash
# Restore from custom format
pg_restore -d mydb mydb.dump

# Restore specific table
pg_restore -d mydb -t users mydb.dump

# List contents
pg_restore -l mydb.dump

# Parallel restore
pg_restore -d mydb -j 4 mydb.dump

# Clean database first
pg_restore -d mydb --clean mydb.dump

# Create database if not exists
pg_restore -C -d postgres mydb.dump
```

### Restore from SQL
```bash
# Restore SQL dump
psql mydb < mydb.sql

# Create database and restore
createdb mydb
psql mydb < mydb.sql

# Single transaction
psql -1 mydb < mydb.sql

# Stop on error
psql --set ON_ERROR_STOP=on mydb < mydb.sql
```

### Automated Backup Script
```bash
#!/bin/bash
# backup.sh

# Configuration
DB_NAME="mydb"
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

# Create backup
pg_dump -Fc "$DB_NAME" > "$BACKUP_DIR/${DB_NAME}_${DATE}.dump"

# Remove old backups
find "$BACKUP_DIR" -name "${DB_NAME}_*.dump" -mtime +$RETENTION_DAYS -delete

# Log
echo "Backup completed: ${DB_NAME}_${DATE}.dump"
```

### Point-in-Time Recovery (PITR)
```bash
# Enable WAL archiving (postgresql.conf)
wal_level = replica
archive_mode = on
archive_command = 'cp %p /archive/%f'
max_wal_senders = 3

# Base backup
pg_basebackup -D /backup/base -Ft -z -P

# Restore to point in time
# 1. Stop PostgreSQL
# 2. Restore base backup
# 3. Create recovery.conf with recovery_target_time
# 4. Start PostgreSQL
```


---

Continued in [postgresql-administration-cont.md](postgresql-administration-cont.md)

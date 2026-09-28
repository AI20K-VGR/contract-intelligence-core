# PostgreSQL psql CLI

Command-line interface for PostgreSQL: connection, meta-commands, scripting, and interactive usage.

## Connection

### Basic Connection
```bash
# Connect to database
psql -U username -d database -h hostname -p 5432

# Connect using URI
psql postgresql://username:password@hostname:5432/database

# Environment variables
export PGUSER=postgres
export PGPASSWORD=mypassword
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=mydb
psql
```

### Password File (~/.pgpass)
```bash
# Format: hostname:port:database:username:password
# chmod 600 ~/.pgpass
localhost:5432:mydb:postgres:mypassword
*.example.com:5432:*:appuser:apppass
```

### SSL Connection
```bash
# Require SSL
psql "host=hostname sslmode=require user=username dbname=database"

# Verify certificate
psql "host=hostname sslmode=verify-full \
  sslcert=/path/to/client.crt \
  sslkey=/path/to/client.key \
  sslrootcert=/path/to/ca.crt"
```

## Essential Meta-Commands

### Database Navigation
```bash
\l or \list                    # List databases
\l+                            # List with sizes
\c database                    # Connect to database
\c database username           # Connect as user
\conninfo                      # Connection info
```

### Schema Inspection
```bash
\dn                            # List schemas
\dt                            # List tables
\dt+                           # Tables with sizes
\dt *.*                        # All tables, all schemas
\di                            # List indexes
\dv                            # List views
\dm                            # List materialized views
\ds                            # List sequences
\df                            # List functions
```

### Object Description
```bash
\d tablename                   # Describe table
\d+ tablename                  # Detailed description
\d indexname                   # Describe index
\df functionname               # Describe function
\du                            # List users/roles
\dp tablename                  # Show permissions
```

### Output Formatting
```bash
\x                             # Toggle expanded output
\x on                          # Enable expanded
\x off                         # Disable expanded
\a                             # Toggle aligned output
\t                             # Toggle tuples only
\H                             # HTML output
\pset format csv               # CSV format
\pset null '[NULL]'            # Show NULL values
```

### Execution Commands
```bash
\i filename.sql                # Execute SQL file
\o output.txt                  # Redirect output to file
\o                             # Stop redirecting
\! command                     # Execute shell command
\timing                        # Toggle timing
\q                             # Quit
```

## psql Command-Line Options

```bash
# Connection
-h hostname                    # Host
-p port                        # Port (default 5432)
-U username                    # Username
-d database                    # Database
-W                             # Prompt for password

# Execution
-c "SQL"                       # Execute command and exit
-f file.sql                    # Execute file
--command="SQL"                # Execute command

# Output
-t                             # Tuples only (no headers)
-A                             # Unaligned output
-F ","                         # Field separator
-o output.txt                  # Output to file
-q                             # Quiet mode
-x                             # Expanded output

# Script options
-1                             # Execute as transaction
--on-error-stop                # Stop on error
-v variable=value              # Set variable
-L logfile.log                 # Log session
```

## Running SQL

### Interactive Queries
```sql
-- Simple query
SELECT * FROM users;

-- Multi-line (ends with semicolon)
SELECT id, name, email
FROM users
WHERE active = true;

-- Edit in editor
\e

-- Repeat last query
\g

-- Send to file
\g output.txt
```

### Variables
```bash
# Set variable
\set myvar 'value'
\set limit 10

# Use variable
SELECT * FROM users LIMIT :limit;

# String variable (quoted)
\set username 'alice'
SELECT * FROM users WHERE name = :'username';

# Show all variables
\set

# Unset variable
\unset myvar
```

### Scripts
```sql
-- script.sql
\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE
);

INSERT INTO users (name, email) VALUES
  ('Alice', 'alice@example.com'),
  ('Bob', 'bob@example.com');

COMMIT;

\echo 'Script completed!'
```

```bash
# Execute script
psql -d mydb -f script.sql

# With error stopping
psql -d mydb -f script.sql --on-error-stop

# In single transaction
psql -d mydb -1 -f script.sql
```

## Data Import/Export

### COPY (Server-side)
```sql
-- Export to CSV
COPY users TO '/tmp/users.csv' WITH (FORMAT CSV, HEADER);

-- Import from CSV
COPY users FROM '/tmp/users.csv' WITH (FORMAT CSV, HEADER);

-- Query to file
COPY (SELECT * FROM users WHERE active = true)
TO '/tmp/active_users.csv' WITH (FORMAT CSV, HEADER);
```

### \copy (Client-side)
```bash
# Export (from psql)
\copy users TO 'users.csv' WITH (FORMAT CSV, HEADER)

# Export query results
\copy (SELECT * FROM users WHERE active = true) TO 'active.csv' CSV HEADER

# Import
\copy users FROM 'users.csv' WITH (FORMAT CSV, HEADER)

# To stdout
\copy users TO STDOUT CSV HEADER > users.csv
```

### pg_dump / pg_restore
```bash
# Dump database
pg_dump mydb > mydb.sql
pg_dump -d mydb -Fc > mydb.dump  # Custom format

# Dump specific table
pg_dump -t users mydb > users.sql

# Schema only
pg_dump -s mydb > schema.sql

# Data only
pg_dump -a mydb > data.sql

# Restore
psql mydb < mydb.sql
pg_restore -d mydb mydb.dump
```


---

Continued in [postgresql-psql-cli-cont.md](postgresql-psql-cli-cont.md)

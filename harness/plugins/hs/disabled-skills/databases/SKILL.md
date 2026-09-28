---
name: hs:databases
injectable: true
description: Design schemas, write queries for MongoDB and PostgreSQL. Use for database design, SQL/NoSQL queries, aggregation pipelines, indexes, migrations, replication, performance optimization, psql CLI.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch]
argument-hint: "[query or schema task]"
paths: ["**/*.sql", "**/migrations/**"]
metadata:
  compliance-tier: workflow
---

# Databases Skill

Unified guide for working with MongoDB (document-oriented) and PostgreSQL (relational) databases. Choose the right database for your use case and master both systems.

**Probe-first ★** (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/agent-operational-discipline.md` — the priority discipline): whether an index helps, what a query plan is, how a migration locks —
RUN it (`EXPLAIN [ANALYZE]`, a real migration on a scratch DB) before you commit to it; reasoning about the planner is a *hypothesis*, NOT a probe. An unrun cost / plan / lock claim is `[ASSUMED]`, never OBSERVED.

## When to Use This Skill

Use when:
- Designing database schemas and data models
- Writing queries (SQL or MongoDB query language)
- Building aggregation pipelines or complex joins
- Optimizing indexes and query performance
- Implementing database migrations
- Setting up replication, sharding, or clustering
- Configuring backups and disaster recovery
- Managing database users and permissions
- Analyzing slow queries and performance issues
- Administering production database deployments

## Reference Navigation

### Database Design
- **[db-design.md](db-design.md)** - Activate when user requests: Database/table design for transactional (OLTP), analytics (OLAP), create or extend schema, design fact/dimension tables, analyze/review CSV/JSON/SQL files to create tables, or need advice on data storage structure.

### MongoDB References
- **[mongodb-crud.md](references/mongodb-crud.md)** - CRUD operations, query operators, atomic updates
- **[mongodb-aggregation.md](references/mongodb-aggregation.md)** - Aggregation pipeline, stages, operators, patterns
- **[mongodb-indexing.md](references/mongodb-indexing.md)** - Index types, compound indexes, performance optimization
- **[mongodb-atlas.md](references/mongodb-atlas.md)** - Atlas cloud setup, clusters, monitoring, search

### PostgreSQL References
- **[postgresql-queries.md](references/postgresql-queries.md)** - SELECT, JOINs, subqueries, CTEs, window functions
- **[postgresql-psql-cli.md](references/postgresql-psql-cli.md)** - psql commands, meta-commands, scripting
- **[postgresql-performance.md](references/postgresql-performance.md)** - EXPLAIN, query optimization, vacuum, indexes
- **[postgresql-administration.md](references/postgresql-administration.md)** - User management, backups, replication, maintenance

## Python Utilities

Database utility scripts in `scripts/`:
- **db_migrate.py** - Generate and apply migrations for both databases (MongoDB and PostgreSQL)
- **db_backup.py** - Backup and restore MongoDB and PostgreSQL
- **db_performance_check.py** - Analyze slow queries and recommend indexes

```bash
# Generate migration
python scripts/db_migrate.py --db mongodb generate "add_user_index"

# Run backup
python scripts/db_backup.py --db postgres --backup-dir /backups/ backup --uri $POSTGRES_URI --database mydb

# Check performance
python scripts/db_performance_check.py --db mongodb --uri $MONGO_URI --threshold 100
```

## Resources

- MongoDB: https://www.mongodb.com/docs/
- PostgreSQL: https://www.postgresql.org/docs/
- MongoDB University: https://learn.mongodb.com/
- PostgreSQL Tutorial: https://www.postgresqltutorial.com/

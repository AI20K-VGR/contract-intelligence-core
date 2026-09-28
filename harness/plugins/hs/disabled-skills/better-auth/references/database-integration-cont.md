# Database Integration (continued 2/3)

## Schema Generation

### Using CLI

```bash
# Generate schema files
npx @better-auth/cli generate

# Specify adapter
npx @better-auth/cli generate --adapter drizzle
npx @better-auth/cli generate --adapter prisma

# Specify output
npx @better-auth/cli generate --output ./db/schema.ts
```

### Auto-migrate (Kysely only)

```bash
npx @better-auth/cli migrate
```

For other ORMs, apply generated schema manually.

## Custom Fields

Add custom fields to user table:

```ts
export const auth = betterAuth({
  user: {
    additionalFields: {
      role: {
        type: "string",
        required: false,
        defaultValue: "user"
      },
      phoneNumber: {
        type: "string",
        required: false
      },
      subscriptionTier: {
        type: "string",
        required: false
      }
    }
  }
});
```

After adding fields:
```bash
npx @better-auth/cli generate
```

Update user with custom fields:
```ts
await authClient.updateUser({
  role: "admin",
  phoneNumber: "+1234567890"
});
```

## Plugin Schema Extensions

Plugins add own tables/fields. Regenerate schema after adding plugins:

```bash
npx @better-auth/cli generate
```

### Two-Factor Plugin Tables

- `twoFactor`: Stores TOTP secrets, backup codes

### Passkey Plugin Tables

- `passkey`: Stores WebAuthn credentials

### Organization Plugin Tables

- `organization`: Organization data
- `member`: Organization members
- `invitation`: Pending invitations

## Migration Strategies

### Development

```bash
# Generate schema
npx @better-auth/cli generate

# Apply migrations (Kysely)
npx @better-auth/cli migrate

# Or manual (Prisma)
npx prisma migrate dev

# Or manual (Drizzle)
npx drizzle-kit push
```

### Production

```bash
# Review generated migration
npx @better-auth/cli generate

# Test in staging
# Apply to production with your ORM's migration tool

# Prisma
npx prisma migrate deploy

# Drizzle
npx drizzle-kit push

# Kysely
npx @better-auth/cli migrate
```

## Connection Pooling

### PostgreSQL

```ts
import { Pool } from "pg";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20, // Max connections
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});
```

### MySQL

```ts
import { createPool } from "mysql2/promise";

const pool = createPool({
  connectionString: process.env.DATABASE_URL,
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
});
```

## Database URLs

### PostgreSQL

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
# Or with connection params
DATABASE_URL=postgresql://user:password@localhost:5432/dbname?schema=public&connection_limit=10
```

### MySQL

```env
DATABASE_URL=mysql://user:password@localhost:3306/dbname
```

### SQLite

```env
DATABASE_URL=file:./dev.db
# Or in-memory
DATABASE_URL=:memory:
```

### MongoDB

```env
MONGODB_URI=mongodb://localhost:27017/dbname
# Or Atlas
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/dbname
```

## Performance Optimization

### Indexes

CLI auto-generates essential indexes:
- `user.email` (unique)
- `session.userId`
- `account.userId`
- `account.providerId, accountId` (unique)

Add custom indexes for performance:
```sql
CREATE INDEX idx_session_expires ON session(expiresAt);
CREATE INDEX idx_user_created ON user(createdAt);
```

### Query Optimization

```ts
// Use connection pooling
// Enable query caching where applicable
// Monitor slow queries

export const auth = betterAuth({
  advanced: {
    defaultCookieAttributes: {
      sameSite: "lax",
      secure: true,
      httpOnly: true
    }
  }
});
```

## Backup Strategies

### PostgreSQL

```bash
# Backup
pg_dump dbname > backup.sql

# Restore
psql dbname < backup.sql
```

### MySQL

```bash
# Backup
mysqldump -u root -p dbname > backup.sql

# Restore
mysql -u root -p dbname < backup.sql
```

### SQLite

```bash
# Copy file
cp dev.db dev.db.backup

# Or use backup command
sqlite3 dev.db ".backup backup.db"
```

### MongoDB

```bash
# Backup
mongodump --db=dbname --out=./backup

# Restore
mongorestore --db=dbname ./backup/dbname
```

## Best Practices

1. **Environment Variables**: Store credentials in env vars, never commit
2. **Connection Pooling**: Use pools for PostgreSQL/MySQL in production
3. **Migrations**: Use ORM migration tools, not raw SQL in production
4. **Indexes**: Add indexes for frequently queried fields
5. **Backups**: Automate daily backups in production
6. **SSL**: Use SSL/TLS for database connections in production
7. **Schema Sync**: Keep schema in sync across environments
8. **Testing**: Use separate database for tests (in-memory SQLite ideal)
9. **Monitoring**: Monitor query performance and connection pool usage
10. **Cleanup**: Periodically clean expired sessions/verifications


---

Continued in [database-integration-cont2.md](database-integration-cont2.md)

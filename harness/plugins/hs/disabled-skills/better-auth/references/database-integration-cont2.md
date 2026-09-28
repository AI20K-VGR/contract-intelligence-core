# Database Integration (continued 3/3)

## Troubleshooting

### Connection Errors

```ts
// Add connection timeout
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  connectionTimeoutMillis: 5000
});
```

### Schema Mismatch

```bash
# Regenerate schema
npx @better-auth/cli generate

# Apply migrations
# For Prisma: npx prisma migrate dev
# For Drizzle: npx drizzle-kit push
```

### Migration Failures

- Check database credentials
- Verify database server is running
- Check for schema conflicts
- Review migration SQL manually

### Performance Issues

- Add indexes on foreign keys
- Enable connection pooling
- Monitor slow queries
- Consider read replicas for heavy read workloads

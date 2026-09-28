# PostgreSQL Performance Optimization (continued 3/3)

## Best Practices

1. **Index strategy**
   - Index foreign keys
   - Index WHERE clause columns
   - Index ORDER BY columns
   - Use composite indexes for multi-column queries
   - Keep index count reasonable (5-10 per table)

2. **Query optimization**
   - Use EXPLAIN ANALYZE
   - Avoid SELECT *
   - Use LIMIT when possible
   - Filter before joining
   - Use appropriate join type

3. **Statistics**
   - Regular ANALYZE
   - Increase statistics target for skewed distributions
   - Monitor autovacuum

4. **Monitoring**
   - Enable pg_stat_statements
   - Log slow queries
   - Monitor index usage
   - Check table bloat

5. **Maintenance**
   - Regular VACUUM
   - REINDEX periodically
   - Update PostgreSQL version
   - Monitor disk space

6. **Configuration**
   - Tune memory settings
   - Adjust for workload (OLTP vs OLAP)
   - Use connection pooling
   - Enable query logging

7. **Testing**
   - Test queries with production-like data volume
   - Benchmark before/after changes
   - Monitor production metrics

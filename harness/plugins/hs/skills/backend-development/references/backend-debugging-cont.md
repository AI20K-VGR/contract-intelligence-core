# Backend Debugging Strategies (continued 2/4)

## Database Debugging

### SQL Query Debugging (PostgreSQL)

**1. EXPLAIN ANALYZE**
```sql
-- Show query execution plan and actual timings
EXPLAIN ANALYZE
SELECT u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id, u.name
ORDER BY order_count DESC
LIMIT 10;

-- Look for:
-- - Seq Scan on large tables (missing indexes)
-- - High execution time
-- - Large row estimates
```

**2. Enable Slow Query Logging**
```sql
-- PostgreSQL configuration
ALTER DATABASE mydb SET log_min_duration_statement = 1000; -- Log queries >1s

-- Check slow queries
SELECT query, calls, total_exec_time, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**3. Active Query Monitoring**
```sql
-- See currently running queries
SELECT pid, now() - query_start as duration, query, state
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC;

-- Kill a long-running query
SELECT pg_terminate_backend(pid);
```

### MongoDB Debugging

**1. Explain Query Performance**
```javascript
db.users.find({ email: 'test@example.com' }).explain('executionStats')

// Look for:
// - totalDocsExamined vs nReturned (should be close)
// - COLLSCAN (collection scan - needs index)
// - executionTimeMillis (should be low)
```

**2. Profile Slow Queries**
```javascript
// Enable profiling for queries >100ms
db.setProfilingLevel(1, { slowms: 100 })

// View slow queries
db.system.profile.find().limit(5).sort({ ts: -1 }).pretty()

// Disable profiling
db.setProfilingLevel(0)
```

### Redis Debugging

**1. Monitor Commands**
```bash
# See all commands in real-time
redis-cli MONITOR

# Check slow log
redis-cli SLOWLOG GET 10

# Set slow log threshold (microseconds)
redis-cli CONFIG SET slowlog-log-slower-than 10000
```

**2. Memory Analysis**
```bash
# Memory usage by key pattern
redis-cli --bigkeys

# Memory usage details
redis-cli INFO memory

# Analyze specific key
redis-cli MEMORY USAGE mykey
```

## API Debugging

### HTTP Request Debugging

**1. cURL Testing**
```bash
# Verbose output with headers
curl -v https://api.example.com/users

# Include response headers
curl -i https://api.example.com/users

# POST with JSON
curl -X POST https://api.example.com/users \
  -H "Content-Type: application/json" \
  -d '{"name":"John","email":"john@example.com"}' \
  -v

# Save response to file
curl https://api.example.com/users -o response.json
```

**2. HTTPie (User-Friendly)**
```bash
# Install
pip install httpie

# Simple GET
http GET https://api.example.com/users

# POST with JSON
http POST https://api.example.com/users name=John email=john@example.com

# Custom headers
http GET https://api.example.com/users Authorization:"Bearer token123"
```

**3. Request Logging Middleware**

**Express/Node.js:**
```typescript
import morgan from 'morgan';

// Development
app.use(morgan('dev'));

// Production (JSON format)
app.use(morgan('combined'));

// Custom format
app.use(morgan(':method :url :status :response-time ms - :res[content-length]'));
```

**FastAPI/Python:**
```python
from fastapi import Request
import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    logger.info(
        "request_processed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration * 1000
    )
    return response
```

## Performance Debugging

### CPU Profiling

**Node.js (0x)**
```bash
# Install
npm install -g 0x

# Profile application
0x node app.js

# Open flamegraph in browser
# Identify hot spots (red areas)
```

**Node.js (Clinic.js)**
```bash
# Install
npm install -g clinic

# CPU profiling
clinic doctor -- node app.js

# Heap profiling
clinic heapprofiler -- node app.js

# Event loop analysis
clinic bubbleprof -- node app.js
```

**Python (cProfile)**
```python
import cProfile
import pstats

# Profile function
profiler = cProfile.Profile()
profiler.enable()

# Your code
result = expensive_operation()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)  # Top 10 functions
```

**Go (pprof)**
```go
import (
    "net/http"
    _ "net/http/pprof"
)

func main() {
    // Enable profiling endpoint
    go func() {
        http.ListenAndServe("localhost:6060", nil)
    }()

    // Your application
    startServer()
}

// Profile CPU
// go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

// Profile heap
// go tool pprof http://localhost:6060/debug/pprof/heap
```

### Memory Debugging

**Node.js (Heap Snapshots)**
```typescript
// Take heap snapshot programmatically
import { writeHeapSnapshot } from 'v8';

app.get('/debug/heap', (req, res) => {
    const filename = writeHeapSnapshot();
    res.send(`Heap snapshot written to ${filename}`);
});

// Analyze in Chrome DevTools
// 1. Load heap snapshot
// 2. Compare snapshots to find memory leaks
// 3. Look for detached DOM nodes, large arrays
```

**Python (Memory Profiler)**
```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    large_list = [i for i in range(1000000)]
    return sum(large_list)

# Run with: python -m memory_profiler script.py
# Shows line-by-line memory usage
```


---

Continued in [backend-debugging-cont2.md](backend-debugging-cont2.md)

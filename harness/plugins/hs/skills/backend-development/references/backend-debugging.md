# Backend Debugging Strategies

Debugging techniques, tools, best practices for backend systems (2025).

## Debugging Mindset

### The Scientific Method for Debugging

1. **Observe** - Gather symptoms and data
2. **Hypothesize** - Form theories about the cause
3. **Test** - Verify or disprove theories
4. **Iterate** - Refine understanding
5. **Fix** - Apply solution
6. **Verify** - Confirm fix works

### Golden Rules

1. **Reproduce first** - Debugging without reproduction is guessing
2. **Simplify the problem** - Isolate variables
3. **Read the logs** - Error messages contain clues
4. **Check assumptions** - "It should work" isn't debugging
5. **Use scientific method** - Avoid random changes
6. **Document findings** - Future you will thank you

## Logging Best Practices

### Structured Logging

**Node.js (Pino - Fastest)**
```typescript
import pino from 'pino';

const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  transport: {
    target: 'pino-pretty',
    options: { colorize: true }
  }
});

// Structured logging with context
logger.info({ userId: '123', action: 'login' }, 'User logged in');

// Error logging with stack trace
try {
  await riskyOperation();
} catch (error) {
  logger.error({ err: error, userId: '123' }, 'Operation failed');
}
```

**Python (Structlog)**
```python
import structlog

logger = structlog.get_logger()

# Structured context
logger.info("user_login", user_id="123", ip="192.168.1.1")

# Error with exception
try:
    risky_operation()
except Exception as e:
    logger.error("operation_failed", user_id="123", exc_info=True)
```

**Go (Zap - High Performance)**
```go
import "go.uber.org/zap"

logger, _ := zap.NewProduction()
defer logger.Sync()

// Structured fields
logger.Info("user logged in",
    zap.String("user_id", "123"),
    zap.String("ip", "192.168.1.1"),
)

// Error logging
if err := riskyOperation(); err != nil {
    logger.Error("operation failed",
        zap.Error(err),
        zap.String("user_id", "123"),
    )
}
```

### Log Levels

| Level | Purpose | Example |
|-------|---------|---------|
| **TRACE** | Very detailed, dev only | Request/response bodies |
| **DEBUG** | Detailed info for debugging | SQL queries, cache hits |
| **INFO** | General informational | User login, API calls |
| **WARN** | Potential issues | Deprecated API usage |
| **ERROR** | Error conditions | Failed API calls, exceptions |
| **FATAL** | Critical failures | Database connection lost |

### What to Log

**✅ DO LOG:**
- Request/response metadata (not bodies in prod)
- Error messages with context
- Performance metrics (duration, size)
- Security events (login, permission changes)
- Business events (orders, payments)

**❌ DON'T LOG:**
- Passwords or secrets
- Credit card numbers
- Personal identifiable information (PII)
- Session tokens
- Full request bodies in production

## Debugging Tools by Language

### Node.js / TypeScript

**1. Chrome DevTools (Built-in)**
```bash
# Run with inspect flag
node --inspect-brk app.js

# Open chrome://inspect in Chrome
# Set breakpoints, step through code
```

**2. VS Code Debugger**
```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "node",
      "request": "launch",
      "name": "Debug Server",
      "skipFiles": ["<node_internals>/**"],
      "program": "${workspaceFolder}/src/index.ts",
      "preLaunchTask": "npm: build",
      "outFiles": ["${workspaceFolder}/dist/**/*.js"]
    }
  ]
}
```

**3. Debug Module**
```typescript
import debug from 'debug';

const log = debug('app:server');
const error = debug('app:error');

log('Starting server on port %d', 3000);
error('Failed to connect to database');

// Run with: DEBUG=app:* node app.js
```

### Python

**1. PDB (Built-in Debugger)**
```python
import pdb

def problematic_function(data):
    # Set breakpoint
    pdb.set_trace()

    # Debugger commands:
    # l - list code
    # n - next line
    # s - step into
    # c - continue
    # p variable - print variable
    # q - quit
    result = process(data)
    return result
```

**2. IPython Debugger (Better)**
```python
from IPython import embed

def problematic_function(data):
    # Drop into IPython shell
    embed()

    result = process(data)
    return result
```

**3. VS Code Debugger**
```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload"],
      "jinja": true
    }
  ]
}
```

### Go

**1. Delve (Standard Debugger)**
```bash
# Install
go install github.com/go-delve/delve/cmd/dlv@latest

# Debug
dlv debug main.go

# Commands:
# b main.main - set breakpoint
# c - continue
# n - next line
# s - step into
# p variable - print variable
# q - quit
```

**2. VS Code Debugger**
```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Launch Package",
      "type": "go",
      "request": "launch",
      "mode": "debug",
      "program": "${workspaceFolder}"
    }
  ]
}
```

### Rust

**1. LLDB/GDB (Native Debuggers)**
```bash
# Build with debug info
cargo build

# Debug with LLDB
rust-lldb ./target/debug/myapp

# Debug with GDB
rust-gdb ./target/debug/myapp
```

**2. VS Code Debugger (CodeLLDB)**
```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "lldb",
      "request": "launch",
      "name": "Debug",
      "program": "${workspaceFolder}/target/debug/myapp",
      "args": [],
      "cwd": "${workspaceFolder}"
    }
  ]
}
```


---

Continued in [backend-debugging-cont.md](backend-debugging-cont.md)

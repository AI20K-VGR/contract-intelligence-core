# Backend Development Mindset (continued 2/2)

## Developer Mindset

### Writing Maintainable Code

**SOLID Principles:**

**S - Single Responsibility** - Class/function does one thing
```typescript
// Bad: User class handles auth + email + logging
class User {
  authenticate() {}
  sendEmail() {}
  logActivity() {}
}

// Good: Separate responsibilities
class User {
  authenticate() {}
}
class EmailService {
  sendEmail() {}
}
class Logger {
  logActivity() {}
}
```

**O - Open/Closed** - Open for extension, closed for modification
```typescript
// Good: Strategy pattern
interface PaymentStrategy {
  process(amount: number): Promise<PaymentResult>;
}

class StripePayment implements PaymentStrategy {
  async process(amount: number) { /* ... */ }
}

class PayPalPayment implements PaymentStrategy {
  async process(amount: number) { /* ... */ }
}
```

### Thinking About Edge Cases

**Common Edge Cases:**
- Empty arrays/collections
- Null/undefined values
- Boundary values (min/max integers)
- Concurrent requests (race conditions)
- Network failures
- Duplicate requests (idempotency)
- Invalid input (SQL injection, XSS)

```typescript
// Good: Handle edge cases explicitly
async function getUsers(limit?: number) {
  // Validate input
  if (limit !== undefined && (limit < 1 || limit > 1000)) {
    throw new Error('Limit must be between 1 and 1000');
  }

  // Handle undefined
  const safeLimit = limit ?? 50;

  // Prevent SQL injection with parameterized query
  const users = await db.query('SELECT * FROM users LIMIT $1', [safeLimit]);

  // Handle empty results
  return users.length > 0 ? users : [];
}
```

### Testing Mindset (TDD/BDD)

**70% happy-path tests drafted by AI, humans focus on edge cases**

**Test-Driven Development (TDD):**
```
1. Write failing test
2. Write minimal code to pass
3. Refactor
4. Repeat
```

**Behavior-Driven Development (BDD):**
```gherkin
Feature: User Registration
  Scenario: User registers with valid email
    Given I am on the registration page
    When I enter "test@example.com" as email
    And I enter "SecurePass123!" as password
    Then I should see "Registration successful"
    And I should receive a welcome email
```

### Observability and Debugging Approach

**100% median ROI, $500k average return** from observability investments

**Three Questions:**
1. **Is it slow?** → Check metrics (response time, DB queries)
2. **Is it broken?** → Check logs (errors, stack traces)
3. **Where is it broken?** → Check traces (distributed systems)

```typescript
// Good: Structured logging with context
logger.error('Payment processing failed', {
  orderId: order.id,
  userId: user.id,
  amount: order.total,
  error: error.message,
  stack: error.stack,
  timestamp: Date.now(),
  ipAddress: req.ip,
});
```

## Collaboration & Communication

### API Contract Design (Treating APIs as Products)

**Principles:**
1. **Versioning** - `/api/v1/users`, `/api/v2/users`
2. **Consistency** - Same patterns across endpoints
3. **Documentation** - OpenAPI/Swagger
4. **Backward compatibility** - Don't break existing clients
5. **Clear error messages** - Help clients fix issues

```typescript
// Good: Consistent API design
GET    /api/v1/users         # List users
GET    /api/v1/users/:id     # Get user
POST   /api/v1/users         # Create user
PUT    /api/v1/users/:id     # Update user
DELETE /api/v1/users/:id     # Delete user

// Consistent error format
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format",
    "field": "email",
    "timestamp": "2025-01-09T12:00:00Z"
  }
}
```

### Database Schema Design Discussions

**Key Considerations:**
- **Normalization vs Denormalization** - Trade-offs for performance
- **Indexing strategy** - Query patterns dictate indexes
- **Migration path** - How to evolve schema without downtime
- **Data types** - VARCHAR(255) vs TEXT, INT vs BIGINT
- **Constraints** - Foreign keys, unique constraints, check constraints

### Code Review Mindset (Prevention-First)

**What to Look For:**
- Security vulnerabilities (SQL injection, XSS)
- Performance issues (N+1 queries, missing indexes)
- Error handling (uncaught exceptions)
- Edge cases (null checks, boundary values)
- Readability (naming, comments for complex logic)
- Tests (coverage for new code)

**Constructive Feedback:**
```
# Good review comment
"This could be vulnerable to SQL injection. Consider using parameterized queries:
`db.query('SELECT * FROM users WHERE id = $1', [userId])`"

# Bad review comment
"This is wrong. Fix it."
```

## Mindset Checklist

- [ ] Think in systems (understand dependencies)
- [ ] Analyze trade-offs (CAP, performance vs maintainability)
- [ ] Design for failure (circuit breakers, retries)
- [ ] Apply SOLID principles
- [ ] Consider edge cases (null, empty, boundaries)
- [ ] Write tests first (TDD/BDD)
- [ ] Log with context (structured logging)
- [ ] Design APIs as products (versioning, docs)
- [ ] Plan database schema evolution
- [ ] Give constructive code reviews

## Resources

- **Domain-Driven Design:** https://martinfowler.com/bliki/DomainDrivenDesign.html
- **CAP Theorem:** https://en.wikipedia.org/wiki/CAP_theorem
- **SOLID Principles:** https://en.wikipedia.org/wiki/SOLID
- **Resilience Patterns:** https://docs.microsoft.com/en-us/azure/architecture/patterns/

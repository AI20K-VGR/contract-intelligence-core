# Backend Testing Strategies (continued 2/2)

## Database Migration Testing

**Critical:** 83% migrations fail without proper testing

```typescript
describe('Database Migrations', () => {
  it('should migrate from v1 to v2 without data loss', async () => {
    // Insert test data in v1 schema
    await db.query(`
      INSERT INTO users (id, email, name)
      VALUES (1, 'test@example.com', 'Test User')
    `);

    // Run migration
    await runMigration('v2-add-created-at.sql');

    // Verify v2 schema
    const result = await db.query('SELECT * FROM users WHERE id = 1');
    expect(result.rows[0]).toMatchObject({
      id: 1,
      email: 'test@example.com',
      name: 'Test User',
      created_at: expect.any(Date),
    });
  });

  it('should rollback migration successfully', async () => {
    await runMigration('v2-add-created-at.sql');
    await rollbackMigration('v2-add-created-at.sql');

    // Verify v1 schema restored
    const columns = await db.query(`
      SELECT column_name FROM information_schema.columns
      WHERE table_name = 'users'
    `);
    expect(columns.rows.map(r => r.column_name)).not.toContain('created_at');
  });
});
```

## Security Testing

### SAST (Static Application Security Testing)

```bash
# SonarQube for code quality + security
sonar-scanner \
  -Dsonar.projectKey=my-backend \
  -Dsonar.sources=src \
  -Dsonar.host.url=http://localhost:9000

# Semgrep for security patterns
semgrep --config auto src/
```

### DAST (Dynamic Application Security Testing)

```bash
# OWASP ZAP for runtime security scanning
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://api.example.com \
  -r zap-report.html
```

### Dependency Scanning (SCA)

```bash
# npm audit for Node.js
npm audit fix

# Snyk for multi-language
snyk test
snyk monitor  # Continuous monitoring
```

## Code Coverage

### Target Metrics (SonarQube Standards)

- **Overall coverage:** 80%+
- **Critical paths:** 100% (authentication, payment, data integrity)
- **New code:** 90%+

### Implementation

```bash
# Vitest with coverage
vitest run --coverage

# Jest with coverage
jest --coverage --coverageThreshold='{"global":{"branches":80,"functions":80,"lines":80}}'
```

## CI/CD Testing Pipeline

```yaml
# GitHub Actions example
name: Test Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Unit Tests
        run: npm run test:unit

      - name: Integration Tests
        run: npm run test:integration

      - name: E2E Tests
        run: npm run test:e2e

      - name: Load Tests
        run: k6 run load-test.js

      - name: Security Scan
        run: npm audit && snyk test

      - name: Coverage Report
        run: npm run test:coverage

      - name: Upload to Codecov
        uses: codecov/codecov-action@v3
```

## Testing Best Practices

1. **Arrange-Act-Assert (AAA) Pattern**
2. **One assertion per test** (when practical)
3. **Descriptive test names** - `should throw error when email is invalid`
4. **Test edge cases** - Empty inputs, boundary values, null/undefined
5. **Clean test data** - Reset database state between tests
6. **Fast tests** - Unit tests < 10ms, Integration < 100ms
7. **Deterministic** - No flaky tests, avoid sleep(), use waitFor()
8. **Independent** - Tests don't depend on execution order

## Testing Checklist

- [ ] Unit tests cover 70% of codebase
- [ ] Integration tests for all API endpoints
- [ ] Contract tests for microservices
- [ ] Load tests configured (k6/Gatling)
- [ ] E2E tests for critical user flows
- [ ] Database migration tests
- [ ] Security scanning in CI/CD (SAST, DAST, SCA)
- [ ] Code coverage reports automated
- [ ] Tests run on every PR
- [ ] Flaky tests eliminated

## Resources

- **Vitest:** https://vitest.dev/
- **Playwright:** https://playwright.dev/
- **k6:** https://k6.io/docs/
- **Pact:** https://docs.pact.io/
- **TestContainers:** https://testcontainers.com/

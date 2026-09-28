# Backend Testing Strategies

Testing approaches, frameworks, quality-assurance practices (2025).

## Test Pyramid (70-20-10 Rule)

```
        /\
       /E2E\     10% - End-to-End Tests
      /------\
     /Integr.\ 20% - Integration Tests
    /----------\
   /   Unit     \ 70% - Unit Tests
  /--------------\
```

**Rationale:**
- Unit tests: Fast, cheap, isolate bugs quickly
- Integration tests: Verify component interactions
- E2E tests: Expensive, slow, but validate real user flows

## Unit Testing

### Frameworks by Language

**TypeScript/JavaScript:**
- **Vitest** - 50% faster than Jest in CI/CD, ESM native
- **Jest** - Mature, large ecosystem, snapshot testing

**Python:**
- **Pytest** - Industry standard, fixtures, parametrization
- **Unittest** - Built-in, standard library

**Go:**
- **testing** - Built-in, table-driven tests
- **testify** - Assertions and mocking

### Best Practices

```typescript
// Good: Test single responsibility
describe('UserService', () => {
  describe('createUser', () => {
    it('should create user with valid data', async () => {
      const userData = { email: 'test@example.com', name: 'Test' };
      const user = await userService.createUser(userData);

      expect(user).toMatchObject(userData);
      expect(user.id).toBeDefined();
    });

    it('should throw error with duplicate email', async () => {
      const userData = { email: 'existing@example.com', name: 'Test' };

      await expect(userService.createUser(userData))
        .rejects.toThrow('Email already exists');
    });

    it('should hash password before storing', async () => {
      const userData = { email: 'test@example.com', password: 'plain123' };
      const user = await userService.createUser(userData);

      expect(user.password).not.toBe('plain123');
      expect(user.password).toMatch(/^\$argon2id\$/);
    });
  });
});
```

### Mocking

```typescript
// Mock external dependencies
jest.mock('./emailService');

it('should send welcome email after user creation', async () => {
  const emailService = require('./emailService');
  emailService.sendWelcomeEmail = jest.fn();

  await userService.createUser({ email: 'test@example.com' });

  expect(emailService.sendWelcomeEmail).toHaveBeenCalledWith('test@example.com');
});
```

## Integration Testing

### API Integration Tests

```typescript
import request from 'supertest';
import { app } from '../app';

describe('POST /api/users', () => {
  beforeAll(async () => {
    await db.connect(); // Real database connection (test DB)
  });

  afterAll(async () => {
    await db.disconnect();
  });

  beforeEach(async () => {
    await db.users.deleteMany({}); // Clean state
  });

  it('should create user and return 201', async () => {
    const response = await request(app)
      .post('/api/users')
      .send({ email: 'test@example.com', name: 'Test User' })
      .expect(201);

    expect(response.body).toMatchObject({
      email: 'test@example.com',
      name: 'Test User',
    });

    // Verify database persistence
    const user = await db.users.findOne({ email: 'test@example.com' });
    expect(user).toBeDefined();
  });

  it('should return 400 for invalid email', async () => {
    await request(app)
      .post('/api/users')
      .send({ email: 'invalid-email', name: 'Test' })
      .expect(400)
      .expect((res) => {
        expect(res.body.error).toBe('Invalid email format');
      });
  });
});
```

### Database Testing with TestContainers

```typescript
import { GenericContainer } from 'testcontainers';

let container;
let db;

beforeAll(async () => {
  // Spin up real PostgreSQL in Docker
  container = await new GenericContainer('postgres:15')
    .withEnvironment({ POSTGRES_PASSWORD: 'test' })
    .withExposedPorts(5432)
    .start();

  const port = container.getMappedPort(5432);
  db = await createConnection({
    host: 'localhost',
    port,
    database: 'test',
    password: 'test',
  });
}, 60000);

afterAll(async () => {
  await container.stop();
});
```

## Contract Testing (Microservices)

### Pact (Consumer-Driven Contracts)

```typescript
// Consumer test
import { Pact } from '@pact-foundation/pact';

const provider = new Pact({
  consumer: 'UserService',
  provider: 'AuthService',
});

describe('Auth Service Contract', () => {
  beforeAll(() => provider.setup());
  afterEach(() => provider.verify());
  afterAll(() => provider.finalize());

  it('should validate user token', async () => {
    await provider.addInteraction({
      state: 'user token exists',
      uponReceiving: 'a request to validate token',
      withRequest: {
        method: 'POST',
        path: '/auth/validate',
        headers: { 'Content-Type': 'application/json' },
        body: { token: 'valid-token-123' },
      },
      willRespondWith: {
        status: 200,
        body: { valid: true, userId: '123' },
      },
    });

    const response = await authClient.validateToken('valid-token-123');
    expect(response.valid).toBe(true);
  });
});
```

## Load Testing

### Tools Comparison

**k6** (Modern, Developer-Friendly)
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 }, // Ramp up to 100 users
    { duration: '5m', target: 100 }, // Stay at 100 users
    { duration: '2m', target: 0 },   // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% requests under 500ms
  },
};

export default function () {
  const res = http.get('https://api.example.com/users');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
  sleep(1);
}
```

**Gatling** (JVM-based, Advanced Scenarios)
**JMeter** (GUI-based, Traditional)

### Performance Thresholds

- **Response time:** p95 < 500ms, p99 < 1s
- **Throughput:** 1000+ req/sec (target based on SLA)
- **Error rate:** < 1%
- **Concurrent users:** Test at 2x expected peak

## E2E Testing

### Playwright (Modern, Multi-Browser)

```typescript
import { test, expect } from '@playwright/test';

test('user can register and login', async ({ page }) => {
  // Navigate to registration page
  await page.goto('https://app.example.com/register');

  // Fill registration form
  await page.fill('input[name="email"]', 'test@example.com');
  await page.fill('input[name="password"]', 'SecurePass123!');
  await page.click('button[type="submit"]');

  // Verify redirect to dashboard
  await expect(page).toHaveURL('/dashboard');
  await expect(page.locator('h1')).toContainText('Welcome');

  // Verify API call was made
  const response = await page.waitForResponse('/api/users');
  expect(response.status()).toBe(201);
});
```


---

Continued in [backend-testing-cont.md](backend-testing-cont.md)

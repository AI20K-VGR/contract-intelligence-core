# Backend Code Quality

SOLID principles, design patterns, clean code, refactoring (2025).

## SOLID Principles

### Single Responsibility Principle (SRP)

**Concept:** Class/module should have one reason to change

**Bad:**
```typescript
class User {
  saveToDatabase() { /* ... */ }
  sendWelcomeEmail() { /* ... */ }
  generateReport() { /* ... */ }
  validateInput() { /* ... */ }
}
```

**Good:**
```typescript
class User {
  constructor(public id: string, public email: string, public name: string) {}
}

class UserRepository {
  async save(user: User) { /* ... */ }
  async findById(id: string) { /* ... */ }
}

class EmailService {
  async sendWelcomeEmail(user: User) { /* ... */ }
}

class UserValidator {
  validate(userData: any) { /* ... */ }
}

class ReportGenerator {
  generateUserReport(user: User) { /* ... */ }
}
```

### Open/Closed Principle (OCP)

**Concept:** Open for extension, closed for modification

**Bad:**
```typescript
class PaymentProcessor {
  process(amount: number, method: string) {
    if (method === 'stripe') {
      // Stripe logic
    } else if (method === 'paypal') {
      // PayPal logic
    }
    // Adding new payment method requires modifying this class
  }
}
```

**Good (Strategy Pattern):**
```typescript
interface PaymentStrategy {
  process(amount: number): Promise<PaymentResult>;
}

class StripePayment implements PaymentStrategy {
  async process(amount: number) {
    // Stripe-specific logic
    return { success: true, transactionId: '...' };
  }
}

class PayPalPayment implements PaymentStrategy {
  async process(amount: number) {
    // PayPal-specific logic
    return { success: true, transactionId: '...' };
  }
}

class PaymentProcessor {
  constructor(private strategy: PaymentStrategy) {}

  async process(amount: number) {
    return this.strategy.process(amount);
  }
}

// Usage
const processor = new PaymentProcessor(new StripePayment());
await processor.process(100);
```

### Liskov Substitution Principle (LSP)

**Concept:** Subtypes must be substitutable for base types

**Bad:**
```typescript
class Bird {
  fly() { /* ... */ }
}

class Penguin extends Bird {
  fly() {
    throw new Error('Penguins cannot fly!');
  }
}

// Violates LSP - Penguin breaks Bird contract
```

**Good:**
```typescript
interface Bird {
  move(): void;
}

class FlyingBird implements Bird {
  move() {
    this.fly();
  }
  private fly() { /* ... */ }
}

class Penguin implements Bird {
  move() {
    this.swim();
  }
  private swim() { /* ... */ }
}
```

### Interface Segregation Principle (ISP)

**Concept:** Clients shouldn't depend on interfaces they don't use

**Bad:**
```typescript
interface Worker {
  work(): void;
  eat(): void;
  sleep(): void;
}

class Robot implements Worker {
  work() { /* ... */ }
  eat() { throw new Error('Robots don't eat'); }
  sleep() { throw new Error('Robots don't sleep'); }
}
```

**Good:**
```typescript
interface Workable {
  work(): void;
}

interface Eatable {
  eat(): void;
}

interface Sleepable {
  sleep(): void;
}

class Human implements Workable, Eatable, Sleepable {
  work() { /* ... */ }
  eat() { /* ... */ }
  sleep() { /* ... */ }
}

class Robot implements Workable {
  work() { /* ... */ }
}
```

### Dependency Inversion Principle (DIP)

**Concept:** Depend on abstractions, not concretions

**Bad:**
```typescript
class MySQLDatabase {
  query(sql: string) { /* ... */ }
}

class UserService {
  private db = new MySQLDatabase(); // Tight coupling

  async getUser(id: string) {
    return this.db.query(`SELECT * FROM users WHERE id = ${id}`);
  }
}
```

**Good (Dependency Injection):**
```typescript
interface Database {
  query(sql: string, params: any[]): Promise<any>;
}

class MySQLDatabase implements Database {
  async query(sql: string, params: any[]) { /* ... */ }
}

class PostgreSQLDatabase implements Database {
  async query(sql: string, params: any[]) { /* ... */ }
}

class UserService {
  constructor(private db: Database) {} // Injected dependency

  async getUser(id: string) {
    return this.db.query('SELECT * FROM users WHERE id = $1', [id]);
  }
}

// Usage
const db = new PostgreSQLDatabase();
const userService = new UserService(db);
```


---

Continued in [backend-code-quality-cont.md](backend-code-quality-cont.md)

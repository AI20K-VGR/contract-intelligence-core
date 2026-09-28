# Backend Code Quality (continued 2/3)

## Design Patterns

### Repository Pattern

**Concept:** Abstraction layer between business logic and data access

```typescript
// Domain entity
class User {
  constructor(
    public id: string,
    public email: string,
    public name: string,
  ) {}
}

// Repository interface
interface UserRepository {
  findById(id: string): Promise<User | null>;
  findByEmail(email: string): Promise<User | null>;
  save(user: User): Promise<void>;
  delete(id: string): Promise<void>;
}

// Implementation
class PostgresUserRepository implements UserRepository {
  constructor(private db: Database) {}

  async findById(id: string): Promise<User | null> {
    const row = await this.db.query('SELECT * FROM users WHERE id = $1', [id]);
    return row ? new User(row.id, row.email, row.name) : null;
  }

  async save(user: User): Promise<void> {
    await this.db.query(
      'INSERT INTO users (id, email, name) VALUES ($1, $2, $3)',
      [user.id, user.email, user.name]
    );
  }

  // Other methods...
}

// Service layer uses repository
class UserService {
  constructor(private userRepo: UserRepository) {}

  async getUser(id: string) {
    return this.userRepo.findById(id);
  }
}
```

### Factory Pattern

**Concept:** Create objects without specifying exact class

```typescript
interface Notification {
  send(message: string): Promise<void>;
}

class EmailNotification implements Notification {
  async send(message: string) {
    console.log(`Email sent: ${message}`);
  }
}

class SMSNotification implements Notification {
  async send(message: string) {
    console.log(`SMS sent: ${message}`);
  }
}

class PushNotification implements Notification {
  async send(message: string) {
    console.log(`Push notification sent: ${message}`);
  }
}

class NotificationFactory {
  static create(type: 'email' | 'sms' | 'push'): Notification {
    switch (type) {
      case 'email':
        return new EmailNotification();
      case 'sms':
        return new SMSNotification();
      case 'push':
        return new PushNotification();
      default:
        throw new Error(`Unknown notification type: ${type}`);
    }
  }
}

// Usage
const notification = NotificationFactory.create('email');
await notification.send('Hello!');
```

### Decorator Pattern

**Concept:** Add behavior to objects dynamically

```typescript
interface Coffee {
  cost(): number;
  description(): string;
}

class SimpleCoffee implements Coffee {
  cost() {
    return 10;
  }

  description() {
    return 'Simple coffee';
  }
}

class MilkDecorator implements Coffee {
  constructor(private coffee: Coffee) {}

  cost() {
    return this.coffee.cost() + 2;
  }

  description() {
    return `${this.coffee.description()}, milk`;
  }
}

class SugarDecorator implements Coffee {
  constructor(private coffee: Coffee) {}

  cost() {
    return this.coffee.cost() + 1;
  }

  description() {
    return `${this.coffee.description()}, sugar`;
  }
}

// Usage
let coffee: Coffee = new SimpleCoffee();
coffee = new MilkDecorator(coffee);
coffee = new SugarDecorator(coffee);

console.log(coffee.description()); // "Simple coffee, milk, sugar"
console.log(coffee.cost()); // 13
```

### Observer Pattern (Pub/Sub)

**Concept:** Notify multiple objects about state changes

```typescript
interface Observer {
  update(event: any): void;
}

class EventEmitter {
  private observers: Map<string, Observer[]> = new Map();

  subscribe(event: string, observer: Observer) {
    if (!this.observers.has(event)) {
      this.observers.set(event, []);
    }
    this.observers.get(event)!.push(observer);
  }

  emit(event: string, data: any) {
    const observers = this.observers.get(event) || [];
    observers.forEach(observer => observer.update(data));
  }
}

// Observers
class EmailNotifier implements Observer {
  update(event: any) {
    console.log(`Sending email about: ${event.type}`);
  }
}

class LoggerObserver implements Observer {
  update(event: any) {
    console.log(`Logging event: ${JSON.stringify(event)}`);
  }
}

// Usage
const eventEmitter = new EventEmitter();
eventEmitter.subscribe('user.created', new EmailNotifier());
eventEmitter.subscribe('user.created', new LoggerObserver());

eventEmitter.emit('user.created', { type: 'user.created', userId: '123' });
```


---

Continued in [backend-code-quality-cont2.md](backend-code-quality-cont2.md)

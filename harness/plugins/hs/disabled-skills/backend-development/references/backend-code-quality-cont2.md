# Backend Code Quality (continued 3/3)

## Clean Code Practices

### Meaningful Names

**Bad:**
```typescript
function d(a: number, b: number) {
  return a * b * 0.0254;
}
```

**Good:**
```typescript
function calculateAreaInMeters(widthInInches: number, heightInInches: number) {
  const INCHES_TO_METERS = 0.0254;
  return widthInInches * heightInInches * INCHES_TO_METERS;
}
```

### Small Functions

**Bad:**
```typescript
async function processOrder(orderId: string) {
  // 200 lines of code doing everything
  // - validate order
  // - check inventory
  // - process payment
  // - update database
  // - send notifications
  // - generate invoice
}
```

**Good:**
```typescript
async function processOrder(orderId: string) {
  const order = await validateOrder(orderId);
  await checkInventory(order);
  const payment = await processPayment(order);
  await updateOrderStatus(orderId, 'paid');
  await sendConfirmationEmail(order);
  await generateInvoice(order, payment);
}
```

### Avoid Magic Numbers

**Bad:**
```typescript
if (user.age < 18) {
  throw new Error('Too young');
}

setTimeout(fetchData, 86400000);
```

**Good:**
```typescript
const MINIMUM_AGE = 18;
if (user.age < MINIMUM_AGE) {
  throw new Error('Too young');
}

const ONE_DAY_IN_MS = 24 * 60 * 60 * 1000;
setTimeout(fetchData, ONE_DAY_IN_MS);
```

### Error Handling

**Bad:**
```typescript
try {
  const user = await db.findUser(id);
  return user;
} catch (e) {
  console.log(e);
  return null;
}
```

**Good:**
```typescript
try {
  const user = await db.findUser(id);
  if (!user) {
    throw new UserNotFoundError(id);
  }
  return user;
} catch (error) {
  logger.error('Failed to fetch user', {
    userId: id,
    error: error.message,
    stack: error.stack,
  });
  throw new DatabaseError('User fetch failed', { cause: error });
}
```

### Don't Repeat Yourself (DRY)

**Bad:**
```typescript
app.post('/api/users', async (req, res) => {
  if (!req.body.email || !req.body.email.includes('@')) {
    return res.status(400).json({ error: 'Invalid email' });
  }
  // ...
});

app.put('/api/users/:id', async (req, res) => {
  if (!req.body.email || !req.body.email.includes('@')) {
    return res.status(400).json({ error: 'Invalid email' });
  }
  // ...
});
```

**Good:**
```typescript
function validateEmail(email: string) {
  if (!email || !email.includes('@')) {
    throw new ValidationError('Invalid email');
  }
}

app.post('/api/users', async (req, res) => {
  validateEmail(req.body.email);
  // ...
});

app.put('/api/users/:id', async (req, res) => {
  validateEmail(req.body.email);
  // ...
});
```

## Code Refactoring Techniques

### Extract Method

**Before:**
```typescript
function renderOrder(order: Order) {
  console.log('Order Details:');
  console.log(`ID: ${order.id}`);
  console.log(`Total: $${order.total}`);

  console.log('Items:');
  order.items.forEach(item => {
    console.log(`- ${item.name}: $${item.price}`);
  });
}
```

**After:**
```typescript
function renderOrder(order: Order) {
  printOrderHeader(order);
  printOrderItems(order.items);
}

function printOrderHeader(order: Order) {
  console.log('Order Details:');
  console.log(`ID: ${order.id}`);
  console.log(`Total: $${order.total}`);
}

function printOrderItems(items: OrderItem[]) {
  console.log('Items:');
  items.forEach(item => {
    console.log(`- ${item.name}: $${item.price}`);
  });
}
```

### Replace Conditional with Polymorphism

**Before:**
```typescript
function getShippingCost(order: Order) {
  if (order.shippingMethod === 'standard') {
    return 5;
  } else if (order.shippingMethod === 'express') {
    return 15;
  } else if (order.shippingMethod === 'overnight') {
    return 30;
  }
}
```

**After:**
```typescript
interface ShippingMethod {
  getCost(): number;
}

class StandardShipping implements ShippingMethod {
  getCost() {
    return 5;
  }
}

class ExpressShipping implements ShippingMethod {
  getCost() {
    return 15;
  }
}

class OvernightShipping implements ShippingMethod {
  getCost() {
    return 30;
  }
}
```

## Code Quality Checklist

- [ ] SOLID principles applied
- [ ] Functions are small (< 20 lines ideal)
- [ ] Meaningful variable/function names
- [ ] No magic numbers (use constants)
- [ ] Proper error handling (no silent failures)
- [ ] DRY (no code duplication)
- [ ] Comments explain "why", not "what"
- [ ] Design patterns used appropriately
- [ ] Dependency injection for testability
- [ ] Code is readable (readable > clever)

## Resources

- **Clean Code (Book):** Robert C. Martin
- **Refactoring (Book):** Martin Fowler
- **Design Patterns:** https://refactoring.guru/design-patterns
- **SOLID Principles:** https://en.wikipedia.org/wiki/SOLID

## Discount Management

### Discount Validation with Timeout
```typescript
// lib/polar-discounts.ts
const VALIDATION_TIMEOUT_MS = 15000;

export async function validateDiscount(
  code: string,
  productId: string
): Promise<{ valid: boolean; discount?: PolarDiscount; reason?: string }> {
  const sanitizedCode = code.trim().toUpperCase();
  if (!sanitizedCode) {
    return { valid: false, reason: 'Code cannot be empty' };
  }

  const polar = getPolar();
  const env = getPolarEnv();

  try {
    // Race against timeout
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error('Validation timeout')), VALIDATION_TIMEOUT_MS);
    });

    const searchPromise = polar.discounts.list({
      organizationId: env.POLAR_ORGANIZATION_ID,
      query: sanitizedCode,
      limit: 100,
    });

    const result = await Promise.race([searchPromise, timeoutPromise]);

    // Find exact match
    const discount = result.items.find(d =>
      d.code?.toUpperCase() === sanitizedCode
    );

    if (!discount) {
      return { valid: false, reason: 'Code not found' };
    }

    // Check eligibility
    const now = new Date();
    if (discount.startsAt && now < new Date(discount.startsAt)) {
      return { valid: false, reason: `Code starts on ${discount.startsAt}` };
    }
    if (discount.endsAt && now > new Date(discount.endsAt)) {
      return { valid: false, reason: 'Code has expired' };
    }
    if (discount.maxRedemptions && discount.redemptionsCount >= discount.maxRedemptions) {
      return { valid: false, reason: 'Code redemption limit reached' };
    }
    if (!discount.products?.some(p => p.id === productId)) {
      return { valid: false, reason: 'Code not valid for this product' };
    }

    return { valid: true, discount };

  } catch (error) {
    console.error('Discount validation error:', error);
    return { valid: false, reason: 'Validation failed - please try again' };
  }
}
```

### VND Conversion for Discounts
```typescript
const VND_TO_USD_RATE = 25000; // 1 USD = 25,000 VND

export function convertDiscountToVND(discount: PolarDiscount, amountVND: number): number {
  if (discount.type === 'percentage') {
    // Basis points: 1000 = 10%, 10000 = 100%
    const percentage = discount.basisPoints / 10000;
    return Math.round(amountVND * percentage);
  } else {
    // Fixed amount in USD cents → VND
    const amountUSD = discount.amount / 100;
    return Math.round(amountUSD * VND_TO_USD_RATE);
  }
}
```

### Syncing SePay Redemptions to Polar
```typescript
// lib/polar-discount-sync.ts
// When SePay payment completes, decrement Polar discount redemptions

export async function syncPolarDiscountRedemption(
  orderId: string,
  discountId: string,
  discountCode: string
): Promise<{ success: boolean; action: string }> {
  const order = await db.select().from(orders).where(eq(orders.id, orderId)).limit(1);
  if (!order[0]) {
    return { success: false, action: 'order_not_found' };
  }

  // Idempotency check
  const metadata = order[0].metadata ? JSON.parse(order[0].metadata) : {};
  if (metadata.polarDiscountSynced) {
    return { success: true, action: 'already_synced' };
  }

  const polar = getPolar();

  try {
    const discount = await polar.discounts.get({ id: discountId });

    if (discount.maxRedemptions === null || discount.maxRedemptions === undefined) {
      return { success: true, action: 'skipped_unlimited' };
    }

    const currentMax = discount.maxRedemptions;

    if (currentMax <= 1) {
      await polar.discounts.delete({ id: discountId });
      await markOrderSynced(orderId, 'deleted');
    } else {
      await polar.discounts.update({
        id: discountId,
        discountUpdate: { maxRedemptions: currentMax - 1 },
      });
      await markOrderSynced(orderId, 'decremented');
    }

    return { success: true, action: currentMax <= 1 ? 'deleted' : 'decremented' };

  } catch (error: any) {
    if (error.statusCode === 404) {
      // Already deleted - treat as success
      await markOrderSynced(orderId, 'already_deleted');
      return { success: true, action: 'already_deleted' };
    }
    throw error;
  }
}

async function markOrderSynced(orderId: string, action: string) {
  const order = await db.select().from(orders).where(eq(orders.id, orderId)).limit(1);
  const metadata = order[0].metadata ? JSON.parse(order[0].metadata) : {};

  metadata.polarDiscountSynced = true;
  metadata.polarDiscountSyncAction = action;
  metadata.polarDiscountSyncedAt = new Date().toISOString();

  await db.update(orders)
    .set({ metadata: JSON.stringify(metadata) })
    .where(eq(orders.id, orderId));
}
```

## Revenue Tracking with Caching

```typescript
// lib/polar.ts
const REVENUE_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

let revenueCache: {
  data: { totalRevenueCents: number; orderCount: number } | null;
  timestamp: number;
} = { data: null, timestamp: 0 };

export async function getPolarApiRevenue(): Promise<{
  totalRevenueCents: number;
  orderCount: number;
  fromCache: boolean;
}> {
  const now = Date.now();

  // Return cache if valid
  if (revenueCache.data && now - revenueCache.timestamp < REVENUE_CACHE_TTL_MS) {
    return { ...revenueCache.data, fromCache: true };
  }

  const polar = getPolar();
  const env = getPolarEnv();

  try {
    let totalRevenueCents = 0;
    let orderCount = 0;
    let page = 1;
    const maxPages = 100; // Safety limit

    while (page <= maxPages) {
      const response = await polar.orders.list({
        organizationId: env.POLAR_ORGANIZATION_ID,
        page,
        limit: 100,
      });

      for (const order of response.items) {
        if (order.status === 'succeeded') {
          totalRevenueCents += order.netAmount; // After discounts, before tax
          orderCount++;
        }
      }

      if (!response.pagination.hasMore) break;
      page++;
    }

    revenueCache = { data: { totalRevenueCents, orderCount }, timestamp: now };
    return { totalRevenueCents, orderCount, fromCache: false };

  } catch (error) {
    // Return stale cache on error
    if (revenueCache.data) {
      console.warn('Using stale revenue cache due to API error');
      return { ...revenueCache.data, fromCache: true };
    }
    throw error;
  }
}
```

## Error Handling Patterns

### Fail-Open for Non-Critical Operations
```typescript
// Discount creation fails → proceed with full price
try {
  const discount = await createReferralDiscount(productId, amount, referralCode);
  polarDiscountId = discount.id;
} catch (error) {
  console.error('⚠️ Discount creation failed - proceeding with full price:', error);
  // Flag for manual refund investigation
  await flagOrderForReview(orderId, 'discount_creation_failed');
}
```

### Graceful Degradation in Webhooks
```typescript
// Non-critical operations don't block order completion
const operations = [
  { name: 'GitHub invite', fn: () => inviteToGitHub(username, productType) },
  { name: 'Welcome email', fn: () => sendWelcomeEmail(order) },
  { name: 'Discord notification', fn: () => sendSalesNotification(order) },
  { name: 'Tier update', fn: () => updateReferrerTier(referrerId, revenueUsd) },
];

for (const op of operations) {
  try {
    await op.fn();
  } catch (error) {
    console.error(`❌ ${op.name} failed:`, error);
    // Continue processing - don't block order
  }
}
```

### Rate Limit Handling with Exponential Backoff
```typescript
async function callWithRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3
): Promise<T> {
  let attempt = 0;

  while (attempt < maxRetries) {
    try {
      return await fn();
    } catch (error: any) {
      if (error.statusCode === 429) {
        const retryAfter = parseInt(error.headers?.['retry-after'] || '1', 10);
        const delay = retryAfter * 1000 * Math.pow(2, attempt);
        console.log(`Rate limited, retrying in ${delay}ms...`);
        await sleep(delay);
        attempt++;
      } else {
        throw error;
      }
    }
  }

  throw new Error('Max retries exceeded');
}
```

## Database Schema

### Orders Table
```typescript
// db/schema/orders.ts
export const orders = pgTable('orders', {
  id: uuid('id').primaryKey().defaultRandom(),
  userId: uuid('user_id').references(() => users.id),
  email: text('email').notNull(),
  productType: text('product_type').notNull(),
  amount: integer('amount').notNull(), // Final amount in cents
  originalAmount: integer('original_amount'), // Before discounts
  currency: text('currency').default('USD'),
  status: text('status').default('pending'), // pending, completed, failed, refunded
  paymentProvider: text('payment_provider').notNull(), // 'polar' or 'sepay'
  paymentId: text('payment_id'), // External payment ID
  referredBy: uuid('referred_by').references(() => users.id),
  discountAmount: integer('discount_amount').default(0),
  discountRate: numeric('discount_rate', { precision: 5, scale: 2 }),
  metadata: text('metadata'), // JSON with audit trail
  createdAt: timestamp('created_at').defaultNow(),
  updatedAt: timestamp('updated_at').defaultNow(),
});
```

### Webhook Events Table (Idempotency)
```typescript
export const webhookEvents = pgTable('webhook_events', {
  id: uuid('id').primaryKey().defaultRandom(),
  provider: text('provider').notNull(), // 'polar' or 'sepay'
  eventType: text('event_type').notNull(),
  eventId: text('event_id').notNull().unique(), // Idempotency key
  payload: text('payload').notNull(),
  processed: boolean('processed').default(false),
  processedAt: timestamp('processed_at'),
  error: text('error'),
  createdAt: timestamp('created_at').defaultNow(),
});
```

## Metadata Best Practices

### Comprehensive Audit Trail
```typescript
// Store everything needed for debugging and reconciliation
metadata: JSON.stringify({
  // Pricing history
  originalAmount: 9900,

  // Coupon tracking
  couponCode: 'LAUNCH20',
  couponDiscountAmount: 1980,

  // Referral tracking
  referralCode: 'ABC12345',
  referralDiscountAmount: 1584,
  referrerId: 'user-uuid',

  // Customer context
  githubUsername: 'customer',

  // Polar integration
  polarDiscountId: 'disc_xxx',
  polarDiscountSynced: true,
  polarDiscountSyncAction: 'decremented',
  polarDiscountSyncedAt: '2025-01-15T10:30:00Z',

  // Team context (if applicable)
  isTeamPurchase: false,
  teamId: null,
  quantity: 1,
})
```

## Testing

### Unit Tests for Fee Calculation
```typescript
// __tests__/lib/polar-fees.test.ts
describe('calculatePolarFees', () => {
  it('handles zero amount', () => {
    const result = calculatePolarFees(0);
    expect(result.totalFee).toBe(0);
    expect(result.netRevenue).toBe(0);
  });

  it('calculates international one-time correctly', () => {
    // $100 transaction
    const result = calculatePolarFees(10000, true, false);
    expect(result.baseFee).toBe(440);        // 4% + $0.40
    expect(result.internationalFee).toBe(150); // 1.5%
    expect(result.totalFee).toBe(590);
    expect(result.netRevenue).toBe(9410);    // $94.10
  });

  it('preserves per-transaction flat fees in aggregate', () => {
    // Two $100 transactions should each have $0.40 flat fee
    const aggregate = calculateAggregatePolarFees([10000, 10000]);
    const single = calculatePolarFees(20000);

    expect(aggregate.totalFees).toBeGreaterThan(single.totalFee);
    // Difference should be one extra flat fee ($0.40)
    expect(aggregate.totalFees - single.totalFee).toBe(40);
  });
});
```

## Production Checklist

- [ ] Environment variables configured in all environments
- [ ] Sandbox testing completed for all checkout flows
- [ ] Production API key obtained and secured
- [ ] Webhook endpoint deployed and reachable
- [ ] Webhook signature verification implemented
- [ ] Idempotency handling tested with duplicate webhooks
- [ ] Fee calculations verified against Polar dashboard
- [ ] Discount validation timeout configured
- [ ] Error monitoring enabled (Sentry, etc.)
- [ ] Structured logging in place
- [ ] Database indexes on orders.status, orders.paymentProvider
- [ ] Revenue caching configured
- [ ] Rate limit handling implemented
- [ ] Fail-open patterns for non-critical operations
- [ ] Customer email notifications working
- [ ] Refund flow tested end-to-end
- [ ] GitHub access grant/revoke tested
- [ ] Discord sales notifications configured

## Common Pitfalls

1. **Applying discounts in wrong order** - Always coupon first, then referral
2. **Trusting success redirect without verification** - Always verify via API or webhook
3. **Not handling duplicate webhooks** - Use eventId for idempotency
4. **Blocking webhook on non-critical failures** - Wrap in try-catch, log, continue
5. **Hardcoding Polar customer IDs** - Use external_id (your user ID) for lookups
6. **Not setting timeout on discount validation** - API can be slow
7. **Calculating aggregate fees as single transaction** - Each transaction has flat fee
8. **Exposing API keys client-side** - Always server-side
9. **Not preserving original amount in metadata** - Need for audit/debugging
10. **Syncing discount redemptions synchronously** - Can fail; use retry with backoff

# Multi-Provider Order Management Patterns (continued 2/4)

## Commission System

### Commission Schema
```typescript
// db/schema/commissions.ts
export const commissions = pgTable('commissions', {
  id: uuid('id').primaryKey().defaultRandom(),
  orderId: uuid('order_id').references(() => orders.id).notNull(),
  referrerId: uuid('referrer_id').references(() => users.id).notNull(),
  referredUserId: uuid('referred_user_id').references(() => users.id).notNull(),
  referralCodeId: uuid('referral_code_id').references(() => referralCodes.id),

  // Amount in original currency
  orderAmount: integer('order_amount').notNull(),      // Base amount for commission
  orderCurrency: text('order_currency').notNull(),     // 'USD' or 'VND'

  // Commission calculation
  commissionRate: numeric('commission_rate', { precision: 5, scale: 4 }).default('0.20'), // 20%
  commissionAmount: integer('commission_amount').notNull(),
  commissionCurrency: text('commission_currency').notNull(),

  // Normalized USD (for tier tracking)
  orderAmountUsdCents: integer('order_amount_usd_cents'),
  commissionAmountUsdCents: integer('commission_amount_usd_cents'),
  exchangeRateSource: text('exchange_rate_source'),

  // Status
  status: text('status').default('pending'),  // pending, approved, paid, cancelled

  // Timestamps
  createdAt: timestamp('created_at').defaultNow(),
  approvedAt: timestamp('approved_at'),
  paidAt: timestamp('paid_at'),
  cancelledAt: timestamp('cancelled_at'),
});
```

### Creating Commission (Multi-Currency)
```typescript
// lib/commissions.ts
export async function createCommission(params: {
  orderId: string;
  referrerId: string;
  referredUserId: string;
  referralCodeId: string;
  orderAmount: number;
  orderCurrency: 'USD' | 'VND';
  commissionRate?: number;
}): Promise<Commission> {
  const rate = params.commissionRate || 0.20; // Default 20%

  // Calculate commission in original currency
  const commissionAmount = Math.round(params.orderAmount * rate);

  // Convert to USD for tier tracking
  let orderAmountUsdCents: number;
  let commissionAmountUsdCents: number;
  let exchangeRateSource: string;

  if (params.orderCurrency === 'USD') {
    orderAmountUsdCents = params.orderAmount;
    commissionAmountUsdCents = commissionAmount;
    exchangeRateSource = 'native';
  } else {
    const conversion = await convertVndToUsd(params.orderAmount);
    orderAmountUsdCents = conversion.usdCents;
    commissionAmountUsdCents = Math.round(conversion.usdCents * rate);
    exchangeRateSource = conversion.source;
  }

  const [commission] = await db.insert(commissions).values({
    orderId: params.orderId,
    referrerId: params.referrerId,
    referredUserId: params.referredUserId,
    referralCodeId: params.referralCodeId,
    orderAmount: params.orderAmount,
    orderCurrency: params.orderCurrency,
    commissionRate: String(rate),
    commissionAmount,
    commissionCurrency: params.orderCurrency,
    orderAmountUsdCents,
    commissionAmountUsdCents,
    exchangeRateSource,
    status: 'pending',
  }).returning();

  // Update referrer's tier based on USD revenue
  await updateReferrerTier(params.referrerId, orderAmountUsdCents);

  return commission;
}
```

### Referrer Tier System
```typescript
// lib/referrals.ts
const TIER_THRESHOLDS = [
  { tier: 'bronze', minRevenue: 0, commissionRate: 0.20 },
  { tier: 'silver', minRevenue: 50000, commissionRate: 0.25 },     // $500
  { tier: 'gold', minRevenue: 150000, commissionRate: 0.30 },      // $1,500
  { tier: 'platinum', minRevenue: 500000, commissionRate: 0.35 },  // $5,000
];

export async function updateReferrerTier(
  referrerId: string,
  newRevenueUsdCents: number
): Promise<void> {
  const referrer = await db.select()
    .from(users)
    .where(eq(users.id, referrerId))
    .limit(1);

  if (!referrer[0]) return;

  const currentRevenue = referrer[0].referralRevenueUsdCents || 0;
  const totalRevenue = currentRevenue + newRevenueUsdCents;

  // Determine new tier
  let newTier = 'bronze';
  let newRate = 0.20;

  for (const threshold of TIER_THRESHOLDS) {
    if (totalRevenue >= threshold.minRevenue) {
      newTier = threshold.tier;
      newRate = threshold.commissionRate;
    }
  }

  // Update if tier changed
  if (referrer[0].referralTier !== newTier) {
    await db.update(users)
      .set({
        referralTier: newTier,
        referralCommissionRate: String(newRate),
        referralRevenueUsdCents: totalRevenue,
        updatedAt: new Date(),
      })
      .where(eq(users.id, referrerId));

    // Send tier upgrade notification
    if (TIER_THRESHOLDS.findIndex(t => t.tier === newTier) >
        TIER_THRESHOLDS.findIndex(t => t.tier === referrer[0].referralTier)) {
      await sendTierUpgradeEmail(referrerId, newTier, newRate);
    }
  } else {
    // Just update revenue
    await db.update(users)
      .set({
        referralRevenueUsdCents: totalRevenue,
        updatedAt: new Date(),
      })
      .where(eq(users.id, referrerId));
  }
}
```

## Revenue Tracking

### Combined Provider Revenue
```typescript
// lib/revenue.ts
export async function getTotalRevenue(options?: {
  startDate?: Date;
  endDate?: Date;
}): Promise<{
  totalUsdCents: number;
  byProvider: { polar: number; sepay: number };
  orderCount: number;
  averageOrderValueCents: number;
}> {
  let query = db.select()
    .from(orders)
    .where(eq(orders.status, 'completed'));

  if (options?.startDate) {
    query = query.where(gte(orders.createdAt, options.startDate));
  }
  if (options?.endDate) {
    query = query.where(lte(orders.createdAt, options.endDate));
  }

  const completedOrders = await query;

  let totalUsdCents = 0;
  let polarUsdCents = 0;
  let sepayUsdCents = 0;

  for (const order of completedOrders) {
    const normalized = await normalizeOrderToUsd(order);

    totalUsdCents += normalized.amountUsdCents;

    if (order.paymentProvider === 'polar') {
      polarUsdCents += normalized.amountUsdCents;
    } else {
      sepayUsdCents += normalized.amountUsdCents;
    }
  }

  return {
    totalUsdCents,
    byProvider: { polar: polarUsdCents, sepay: sepayUsdCents },
    orderCount: completedOrders.length,
    averageOrderValueCents: completedOrders.length > 0
      ? Math.round(totalUsdCents / completedOrders.length)
      : 0,
  };
}
```

### Maintainer Revenue Calculation
```typescript
// lib/maintainer-revenue.ts
// Calculate actual payout after fees and costs

interface MaintainerRevenue {
  grossRevenue: number;      // Total received
  platformFees: number;      // Polar/Stripe fees
  operatingCosts: number;    // Proportional costs
  taxDeduction: number;      // 17% tax
  netPayout: number;         // Final amount
  currency: 'USD';
}

export async function calculateMaintainerRevenue(
  productIds: string[],
  dateRange: { start: Date; end: Date }
): Promise<MaintainerRevenue> {
  // Get orders for these products
  const orders = await db.select()
    .from(orders)
    .where(and(
      eq(orders.status, 'completed'),
      inArray(orders.productType, productIds),
      gte(orders.createdAt, dateRange.start),
      lte(orders.createdAt, dateRange.end)
    ));

  let grossRevenue = 0;
  let platformFees = 0;

  for (const order of orders) {
    const normalized = await normalizeOrderToUsd(order);
    grossRevenue += normalized.amountUsdCents;

    if (order.paymentProvider === 'polar') {
      const fees = calculatePolarFees(normalized.amountUsdCents);
      platformFees += fees.totalFee;
    }
    // SePay has no platform fees (direct bank transfer)
  }

  // Proportional operating costs (hosting, services, etc.)
  const monthlyOperatingCosts = 50000; // $500/month in cents
  const totalMonthlyRevenue = await getTotalRevenue({
    startDate: dateRange.start,
    endDate: dateRange.end,
  });
  const costRatio = grossRevenue / (totalMonthlyRevenue.totalUsdCents || 1);
  const operatingCosts = Math.round(monthlyOperatingCosts * costRatio);

  // Tax deduction (17%)
  const afterCosts = grossRevenue - platformFees - operatingCosts;
  const taxDeduction = Math.round(afterCosts * 0.17);

  const netPayout = afterCosts - taxDeduction;

  return {
    grossRevenue,
    platformFees,
    operatingCosts,
    taxDeduction,
    netPayout,
    currency: 'USD',
  };
}
```


---

Continued in [multi-provider-order-management-patterns-cont2.md](multi-provider-order-management-patterns-cont2.md)

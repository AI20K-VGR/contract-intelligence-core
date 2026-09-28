# Multi-Provider Order Management Patterns

Production patterns for managing orders across multiple payment providers (Polar + SePay), currency handling, commission systems, and revenue tracking.

## Order Schema Design

### Unified Orders Table
```typescript
// db/schema/orders.ts
import { pgTable, uuid, text, integer, numeric, timestamp, boolean } from 'drizzle-orm/pg-core';

export const orders = pgTable('orders', {
  id: uuid('id').primaryKey().defaultRandom(),
  userId: uuid('user_id').references(() => users.id),
  email: text('email').notNull(),

  // Product info
  productType: text('product_type').notNull(), // 'engineer_kit', 'marketing_kit', 'combo', 'team_*'
  quantity: integer('quantity').default(1),

  // Pricing (stored in provider's currency)
  amount: integer('amount').notNull(),           // Final amount after discounts
  originalAmount: integer('original_amount'),    // Before any discounts
  currency: text('currency').default('USD'),     // 'USD' or 'VND'

  // Status
  status: text('status').default('pending'),     // pending, completed, failed, refunded

  // Provider info
  paymentProvider: text('payment_provider').notNull(), // 'polar' or 'sepay'
  paymentId: text('payment_id'),                 // External payment/transaction ID

  // Referral tracking
  referredBy: uuid('referred_by').references(() => users.id),
  discountAmount: integer('discount_amount').default(0),
  discountRate: numeric('discount_rate', { precision: 5, scale: 2 }),

  // Audit trail (JSON)
  metadata: text('metadata'),

  // Timestamps
  createdAt: timestamp('created_at').defaultNow(),
  updatedAt: timestamp('updated_at').defaultNow(),
});
```

### Provider-Specific Metadata
```typescript
// Polar order metadata
interface PolarOrderMetadata {
  originalAmount: number;
  couponCode?: string;
  couponDiscountAmount?: number;
  referralCode?: string;
  referralDiscountAmount?: number;
  referrerId?: string;
  githubUsername: string;
  polarDiscountId?: string;
  polarDiscountSynced?: boolean;
  polarDiscountSyncAction?: 'decremented' | 'deleted' | 'already_deleted';
  polarDiscountSyncedAt?: string;
  isTeamPurchase?: boolean;
  teamId?: string;
}

// SePay order metadata
interface SepayOrderMetadata {
  originalAmount: number;
  couponCode?: string;
  couponDiscountAmount?: number;
  couponId?: string;              // For Polar discount sync
  referralCode?: string;
  referralDiscountAmount?: number;
  referrerId?: string;
  githubUsername: string;
  vatInvoiceRequested?: boolean;
  encryptedTaxId?: string;
  // Added by webhook
  gateway?: string;
  transactionDate?: string;
  transactionId?: number;
  transferAmount?: number;
  matchMethod?: string;
  content?: string;
}
```

## Currency Conversion

### Multi-Layer Fallback Architecture
```typescript
// lib/currency.ts
const EXCHANGE_RATE_CACHE_TTL = 60 * 60 * 1000; // 1 hour
const FALLBACK_RATES = {
  VND_TO_USD: 24500,  // Conservative estimate
  USD_TO_VND: 24500,
};

interface ExchangeRateCache {
  rates: { VND: number; USD: number };
  timestamp: number;
  source: 'api' | 'cached' | 'expired' | 'fallback';
}

let rateCache: ExchangeRateCache | null = null;

export async function getExchangeRates(): Promise<ExchangeRateCache> {
  const now = Date.now();

  // Layer 1: Fresh cache (< 1 hour)
  if (rateCache && now - rateCache.timestamp < EXCHANGE_RATE_CACHE_TTL) {
    return { ...rateCache, source: 'cached' };
  }

  // Layer 2: Live API
  try {
    const response = await fetch(
      'https://api.exchangerate-api.com/v4/latest/USD',
      { signal: AbortSignal.timeout(5000) }
    );
    const data = await response.json();

    rateCache = {
      rates: { VND: data.rates.VND, USD: 1 },
      timestamp: now,
      source: 'api',
    };
    return rateCache;

  } catch (error) {
    console.warn('Exchange rate API failed:', error);

    // Layer 3: Expired cache (better than nothing)
    if (rateCache) {
      return { ...rateCache, source: 'expired' };
    }

    // Layer 4: Hardcoded fallback
    return {
      rates: { VND: FALLBACK_RATES.VND_TO_USD, USD: 1 },
      timestamp: now,
      source: 'fallback',
    };
  }
}

export async function convertVndToUsd(vndAmount: number): Promise<{
  usdCents: number;
  rate: number;
  source: string;
}> {
  const { rates, source } = await getExchangeRates();
  const usdCents = Math.round((vndAmount / rates.VND) * 100);
  return { usdCents, rate: rates.VND, source };
}

export async function convertUsdToVnd(usdCents: number): Promise<{
  vndAmount: number;
  rate: number;
  source: string;
}> {
  const { rates, source } = await getExchangeRates();
  const vndAmount = Math.round((usdCents / 100) * rates.VND);
  return { vndAmount, rate: rates.VND, source };
}
```

### Normalizing Revenue to USD
```typescript
// For reporting/dashboard - normalize all revenue to USD cents
export async function normalizeOrderToUsd(order: Order): Promise<{
  amountUsdCents: number;
  originalAmountUsdCents: number;
  conversionSource: string;
}> {
  if (order.currency === 'USD') {
    return {
      amountUsdCents: order.amount,
      originalAmountUsdCents: order.originalAmount || order.amount,
      conversionSource: 'native',
    };
  }

  // VND order
  const conversion = await convertVndToUsd(order.amount);
  const originalConversion = order.originalAmount
    ? await convertVndToUsd(order.originalAmount)
    : conversion;

  return {
    amountUsdCents: conversion.usdCents,
    originalAmountUsdCents: originalConversion.usdCents,
    conversionSource: conversion.source,
  };
}
```


---

Continued in [multi-provider-order-management-patterns-cont.md](multi-provider-order-management-patterns-cont.md)

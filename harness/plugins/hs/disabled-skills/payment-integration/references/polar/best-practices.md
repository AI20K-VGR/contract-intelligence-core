# Polar Best Practices

Production-proven SaaS patterns: SDK init, checkout, webhooks, discounts, fee calc, error handling.

## Environment Configuration

### Required Environment Variables
```bash
# Core API
POLAR_API_KEY=polar_at_xxx           # Access token from Polar Dashboard
POLAR_ORGANIZATION_ID=org_xxx        # Your organization ID
POLAR_WEBHOOK_SECRET=whsec_xxx       # Webhook signature verification

# Product IDs (one per product)
POLAR_PRODUCT_ENGINEER_ID=prod_xxx
POLAR_PRODUCT_MARKETING_ID=prod_xxx
POLAR_PRODUCT_COMBO_ID=prod_xxx

# Environment (optional, defaults to production)
POLAR_ENV=production                  # 'production' or 'sandbox'
```

### Lazy Initialization Pattern
```typescript
// lib/polar.ts - Defer validation until first access
import { Polar } from '@polar-sh/sdk';
import { z } from 'zod';

const polarEnvSchema = z.object({
  POLAR_API_KEY: z.string().min(1),
  POLAR_ORGANIZATION_ID: z.string().min(1),
  POLAR_WEBHOOK_SECRET: z.string().min(1),
});

let _polar: Polar | null = null;
let _env: z.infer<typeof polarEnvSchema> | null = null;

export function getPolarEnv() {
  if (!_env) {
    _env = polarEnvSchema.parse({
      POLAR_API_KEY: process.env.POLAR_API_KEY,
      POLAR_ORGANIZATION_ID: process.env.POLAR_ORGANIZATION_ID,
      POLAR_WEBHOOK_SECRET: process.env.POLAR_WEBHOOK_SECRET,
    });
  }
  return _env;
}

export function getPolar() {
  if (!_polar) {
    const env = getPolarEnv();
    const polarEnv = process.env.POLAR_ENV || 'production';
    _polar = new Polar({
      accessToken: env.POLAR_API_KEY,
      server: polarEnv as 'production' | 'sandbox',
    });
  }
  return _polar;
}
```

**Key Benefit:** Module imports succeed at build time; validation deferred until runtime when env vars are available.

## Checkout Flow Implementation

### Standard Checkout API
```typescript
// app/api/checkout/polar/route.ts
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { getPolar, getPolarEnv } from '@/lib/polar';

const checkoutSchema = z.object({
  email: z.string().email(),
  name: z.string().optional(),
  productType: z.enum(['engineer_kit', 'marketing_kit', 'combo']),
  githubUsername: z.string().min(1),
  referralCode: z.string().regex(/^[A-Z0-9]{8}$/).optional(),
  couponCode: z.string().optional(),
});

// Pricing in cents
const PRODUCT_PRICES = {
  engineer_kit: 9900,   // $99
  marketing_kit: 9900,  // $99
  combo: 14900,         // $149
} as const;

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const data = checkoutSchema.parse(body);
    const polar = getPolar();
    const env = getPolarEnv();

    // 1. Normalize email
    const normalizedEmail = data.email.toLowerCase().trim();

    // 2. Validate GitHub username against GitHub API
    const githubValid = await validateGitHubUsername(data.githubUsername);
    if (!githubValid) {
      return NextResponse.json(
        { error: 'Invalid GitHub username' },
        { status: 400 }
      );
    }

    // 3. Get product ID and base price
    const productId = getProductId(data.productType);
    const originalAmount = PRODUCT_PRICES[data.productType];

    // 4. Apply discount hierarchy (order matters!)
    let finalAmount = originalAmount;
    let polarDiscountId: string | undefined;
    let discountMetadata: Record<string, any> = {};

    // Step A: Apply coupon FIRST (if provided)
    if (data.couponCode) {
      const couponResult = await validateAndApplyCoupon(
        data.couponCode,
        productId,
        originalAmount
      );
      if (couponResult.valid) {
        finalAmount = originalAmount - couponResult.discountAmount;
        discountMetadata.couponCode = data.couponCode;
        discountMetadata.couponDiscountAmount = couponResult.discountAmount;
      }
    }

    // Step B: Apply referral discount SECOND (on post-coupon price)
    if (data.referralCode) {
      const referralResult = await calculateReferralDiscount(
        data.referralCode,
        finalAmount, // Applied to post-coupon amount
        normalizedEmail
      );

      if (referralResult.valid && referralResult.discountAmount > 0) {
        // Validate discount calculation
        if (referralResult.discountAmount <= 0) {
          return NextResponse.json(
            { error: 'Invalid discount calculation - contact support' },
            { status: 400 }
          );
        }

        finalAmount -= referralResult.discountAmount;
        discountMetadata.referralCode = data.referralCode;
        discountMetadata.referralDiscountAmount = referralResult.discountAmount;
        discountMetadata.referrerId = referralResult.referrerId;
      }
    }

    // 5. Create order record BEFORE Polar checkout
    const order = await db.insert(orders).values({
      id: crypto.randomUUID(),
      email: normalizedEmail,
      productType: data.productType,
      amount: finalAmount,
      originalAmount,
      currency: 'USD',
      status: 'pending',
      paymentProvider: 'polar',
      referredBy: discountMetadata.referrerId,
      discountAmount: originalAmount - finalAmount,
      metadata: JSON.stringify({
        ...discountMetadata,
        githubUsername: data.githubUsername,
      }),
    }).returning();

    // 6. Create dynamic Polar discount (if referral applied)
    if (discountMetadata.referrerId && discountMetadata.referralDiscountAmount > 0) {
      try {
        const discount = await polar.discounts.create({
          type: 'fixed',
          name: `referral-${order[0].id.slice(0, 8)}`,
          amount: discountMetadata.referralDiscountAmount,
          currency: 'usd',
          duration: 'once',
          maxRedemptions: 1,
          products: [productId],
          metadata: {
            orderId: order[0].id,
            type: 'referral',
            referrerId: discountMetadata.referrerId,
          },
        });
        polarDiscountId = discount.id;
      } catch (error) {
        // FAIL-OPEN: Proceed with full price, flag for manual refund
        console.error('⚠️ Failed to create Polar discount:', error);
      }
    }

    // 7. Create Polar checkout session
    const checkout = await polar.checkouts.create({
      productPriceId: productId,
      customerEmail: normalizedEmail,
      successUrl: `${process.env.NEXT_PUBLIC_URL}/checkout/success?orderId=${order[0].id}`,
      discountId: polarDiscountId,
      allowDiscountCodes: !polarDiscountId, // Prevent stacking
      metadata: {
        orderId: order[0].id,
        githubUsername: data.githubUsername,
        referredBy: discountMetadata.referrerId,
      },
    });

    return NextResponse.json({
      checkoutUrl: checkout.url,
      orderId: order[0].id,
    });

  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json({ error: error.errors }, { status: 400 });
    }
    console.error('Checkout error:', error);
    return NextResponse.json(
      { error: 'Failed to create checkout' },
      { status: 500 }
    );
  }
}
```

### Discount Application Order (Critical)
```
1. Original price (e.g., $99)
2. Apply coupon discount FIRST → post-coupon price (e.g., $79)
3. Apply referral discount SECOND → final price (e.g., $63.20)

Never apply referral to original price if coupon was used!
```

## Webhook Handling

### Signature Verification
```typescript
// app/api/webhooks/polar/route.ts
import { validateEvent } from '@polar-sh/sdk/webhooks';
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const payload = await request.text();
  const headers = Object.fromEntries(request.headers);
  const secret = process.env.POLAR_WEBHOOK_SECRET!;

  let webhookEvent;
  try {
    webhookEvent = validateEvent(payload, headers, secret);
  } catch (error) {
    console.error('Invalid webhook signature:', error);
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 });
  }

  // Extract event ID for idempotency
  const parsedPayload = JSON.parse(payload);
  const eventId = parsedPayload.id || `${parsedPayload.type}-${Date.now()}`;

  // Check for duplicate processing
  const existingEvent = await db.select()
    .from(webhookEvents)
    .where(eq(webhookEvents.eventId, eventId))
    .limit(1);

  if (existingEvent.length > 0) {
    console.log(`Duplicate webhook ignored: ${eventId}`);
    return NextResponse.json({ received: true });
  }

  // Record event BEFORE processing (idempotency)
  await db.insert(webhookEvents).values({
    id: crypto.randomUUID(),
    provider: 'polar',
    eventType: webhookEvent.type,
    eventId,
    payload,
    processed: false,
  });

  try {
    await handleWebhookEvent(webhookEvent);

    // Mark as processed
    await db.update(webhookEvents)
      .set({ processed: true, processedAt: new Date() })
      .where(eq(webhookEvents.eventId, eventId));

  } catch (error) {
    // Log error but don't fail the webhook
    await db.update(webhookEvents)
      .set({
        processed: true,
        processedAt: new Date(),
        error: error instanceof Error ? error.message : 'Unknown error',
      })
      .where(eq(webhookEvents.eventId, eventId));
  }

  return NextResponse.json({ received: true });
}
```

### Event Handlers
```typescript
async function handleWebhookEvent(event: WebhookEvent) {
  switch (event.type) {
    case 'checkout.created':
      // Order already exists from API - just log
      console.log(`Checkout created: ${event.data.id}`);
      break;

    case 'checkout.updated':
      await handleCheckoutUpdated(event.data);
      break;

    case 'order.created':
      await handleOrderCreated(event.data);
      break;

    case 'order.refunded':
      await handleOrderRefunded(event.data);
      break;

    default:
      console.log(`Unhandled event type: ${event.type}`);
  }
}

async function handleOrderCreated(order: PolarOrder) {
  const orderId = order.metadata?.orderId;
  if (!orderId) {
    console.error('Order missing orderId in metadata');
    return;
  }

  const dbOrder = await db.select()
    .from(orders)
    .where(eq(orders.id, orderId))
    .limit(1);

  if (!dbOrder[0]) {
    console.error(`Order not found: ${orderId}`);
    return;
  }

  // 1. Update order status
  await db.update(orders)
    .set({
      status: 'completed',
      paymentId: order.id,
      updatedAt: new Date(),
    })
    .where(eq(orders.id, orderId));

  // 2. Create license (non-blocking)
  try {
    await createLicense(dbOrder[0]);
  } catch (error) {
    console.error('Failed to create license:', error);
  }

  // 3. Send confirmation email (non-blocking)
  try {
    await sendOrderConfirmation(dbOrder[0], order);
  } catch (error) {
    console.error('Failed to send confirmation:', error);
  }

  // 4. Create referral commission (non-blocking)
  if (dbOrder[0].referredBy) {
    try {
      await createCommission(dbOrder[0]);
    } catch (error) {
      console.error('Failed to create commission:', error);
    }
  }

  // 5. Grant GitHub access (non-blocking)
  try {
    const metadata = JSON.parse(dbOrder[0].metadata || '{}');
    await inviteToGitHub(metadata.githubUsername, dbOrder[0].productType);
  } catch (error) {
    console.error('Failed to invite to GitHub:', error);
  }

  // 6. Send Discord notification (non-blocking)
  try {
    await sendSalesNotification(dbOrder[0]);
  } catch (error) {
    console.error('Failed to send Discord notification:', error);
  }
}
```

### Status Mapping
```typescript
function mapPolarStatusToAppStatus(polarStatus: string): string | null {
  switch (polarStatus) {
    case 'succeeded':
      return 'completed';
    case 'failed':
    case 'expired':
      return 'failed';
    case 'open':
    case 'confirmed':
      return null; // Don't update - still pending
    default:
      return null;
  }
}
```

## Fee Calculation

### Platform Fee Structure (Dec 2025)
```typescript
// lib/polar-fees.ts
interface PolarFeeConfig {
  basePercentage: number;     // 4%
  baseFlatCents: number;      // $0.40 per transaction
  internationalSurcharge: number;  // +1.5% for non-US cards
  subscriptionSurcharge: number;   // +0.5% (not for one-time)
}

const POLAR_FEES: PolarFeeConfig = {
  basePercentage: 0.04,
  baseFlatCents: 40,
  internationalSurcharge: 0.015,
  subscriptionSurcharge: 0.005,
};

export function calculatePolarFees(
  amountCents: number,
  isInternational: boolean = true, // Conservative default
  isSubscription: boolean = false
): {
  baseFee: number;
  internationalFee: number;
  subscriptionFee: number;
  totalFee: number;
  netRevenue: number;
} {
  // Handle zero/negative
  if (amountCents <= 0) {
    return { baseFee: 0, internationalFee: 0, subscriptionFee: 0, totalFee: 0, netRevenue: 0 };
  }

  const baseFee = Math.round(amountCents * POLAR_FEES.basePercentage + POLAR_FEES.baseFlatCents);
  const internationalFee = isInternational
    ? Math.round(amountCents * POLAR_FEES.internationalSurcharge)
    : 0;
  const subscriptionFee = isSubscription
    ? Math.round(amountCents * POLAR_FEES.subscriptionSurcharge)
    : 0;

  const totalFee = baseFee + internationalFee + subscriptionFee;
  const netRevenue = amountCents - totalFee;

  return { baseFee, internationalFee, subscriptionFee, totalFee, netRevenue };
}

// Aggregate fees preserve per-transaction flat fees
export function calculateAggregatePolarFees(transactionAmounts: number[]): {
  totalFees: number;
  totalNetRevenue: number;
} {
  let totalFees = 0;
  let totalNetRevenue = 0;

  for (const amount of transactionAmounts) {
    const { totalFee, netRevenue } = calculatePolarFees(amount);
    totalFees += totalFee;
    totalNetRevenue += netRevenue;
  }

  return { totalFees, totalNetRevenue };
}
```

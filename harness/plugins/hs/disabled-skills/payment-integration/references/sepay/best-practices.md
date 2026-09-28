# SePay Best Practices

Production-proven SePay/VietQR bank-transfer patterns: transaction parsing, webhooks, order matching, currency conversion, error handling.

## Environment Configuration

### Required Environment Variables
```bash
# Core API
SEPAY_API_TOKEN=xxx              # Bearer token for SePay API
SEPAY_WEBHOOK_API_KEY=xxx        # API key for webhook authentication
SEPAY_API_URL=https://my.sepay.vn/userapi  # Base URL (optional)

# Bank Account Details
SEPAY_ACCOUNT_NUMBER=0123456789  # Bank account for transfers
SEPAY_ACCOUNT_NAME=COMPANY_NAME  # Account holder name
SEPAY_BANK_NAME=Vietcombank      # Bank name (VietQR recognized)
```

### Product Pricing in VND
```typescript
// lib/sepay.ts
const VND_PRICES = {
  engineer_kit: 2450000,   // ~$100 USD
  marketing_kit: 2450000,  // ~$100 USD
  combo: 3650000,          // ~$149 USD
} as const;

const USD_TO_VND_RATE = 24500; // 1 USD ≈ 24,500 VND
```

## Transaction Content Format

### Standard Format
```
ORDER {order-uuid}
```
Example: `ORDER 4e4635f4-0478-4080-a5c5-48da91f97f1e`

### Team Checkout Format
```
TEAM{8-hex-chars}
```
Example: `TEAM4E4635F4`

### Why These Formats
- UUID ensures global uniqueness
- `ORDER` prefix for easy visual identification
- Short team prefix fits bank memo limits
- Case-insensitive matching handles bank transformations

## QR Code Generation

### VietQR URL Pattern
```typescript
// lib/sepay.ts
export function generateVietQRUrl(
  accountNumber: string,
  bankName: string,
  amount: number,
  content: string
): string {
  const params = new URLSearchParams({
    acc: accountNumber,
    bank: bankName,
    amount: String(Math.floor(amount)), // Integer only
    des: content,
  });

  return `https://qr.sepay.vn/img?${params.toString()}`;
}
```

### Usage Example
```typescript
const qrUrl = generateVietQRUrl(
  process.env.SEPAY_ACCOUNT_NUMBER!,
  process.env.SEPAY_BANK_NAME!,
  2450000,
  `ORDER ${orderId}`
);
// Returns: https://qr.sepay.vn/img?acc=0123456789&bank=Vietcombank&amount=2450000&des=ORDER+uuid
```

## Checkout API Implementation

### Standard SePay Checkout
```typescript
// app/api/checkout/sepay/route.ts
import { NextResponse } from 'next/server';
import { z } from 'zod';

const checkoutSchema = z.object({
  email: z.string().email(),
  name: z.string().optional(),
  productType: z.enum(['engineer_kit', 'marketing_kit', 'combo']),
  githubUsername: z.string().min(1),
  couponCode: z.string().optional(),
  vatInvoiceRequested: z.boolean().optional(),
  taxId: z.string().regex(/^\d{10}$|^\d{13}$/).optional(), // 10 or 13 digits
});

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const data = checkoutSchema.parse(body);

    // 1. Normalize email
    const normalizedEmail = data.email.toLowerCase().trim();

    // 2. Get base price
    const originalAmount = VND_PRICES[data.productType];
    let finalAmount = originalAmount;
    let discountMetadata: Record<string, any> = { originalAmount };

    // 3. CRITICAL: Apply discounts in correct order
    // Step A: Apply coupon FIRST
    if (data.couponCode) {
      const couponResult = await validateCouponForVND(data.couponCode, originalAmount);
      if (couponResult.valid) {
        finalAmount = originalAmount - couponResult.discountAmountVND;
        discountMetadata.couponCode = data.couponCode;
        discountMetadata.couponDiscountAmount = couponResult.discountAmountVND;
        discountMetadata.couponId = couponResult.couponId;
      }
    }

    // Step B: Apply referral SECOND (on post-coupon amount)
    const referralCode = getReferralCodeFromCookie(request);
    if (referralCode) {
      const referralResult = await calculateReferralDiscountVND(
        referralCode,
        finalAmount, // Post-coupon amount
        normalizedEmail
      );
      if (referralResult.valid && referralResult.discountAmount > 0) {
        // Validate calculation
        if (referralResult.discountAmount <= 0) {
          return NextResponse.json(
            { error: 'Invalid discount calculation' },
            { status: 400 }
          );
        }
        finalAmount -= referralResult.discountAmount;
        discountMetadata.referralCode = referralCode;
        discountMetadata.referralDiscountAmount = referralResult.discountAmount;
        discountMetadata.referrerId = referralResult.referrerId;
      }
    }

    // 4. Validate final amount
    if (finalAmount <= 0) {
      return NextResponse.json(
        { error: 'Invalid final amount' },
        { status: 400 }
      );
    }

    // 5. Encrypt sensitive data if VAT invoice requested
    let encryptedTaxId: string | null = null;
    if (data.vatInvoiceRequested && data.taxId) {
      encryptedTaxId = await encrypt(data.taxId);
    }

    // 6. Create order record
    const orderId = crypto.randomUUID();
    const transactionContent = `ORDER ${orderId}`;

    const order = await db.insert(orders).values({
      id: orderId,
      email: normalizedEmail,
      productType: data.productType,
      amount: finalAmount,
      currency: 'VND',
      status: 'pending',
      paymentProvider: 'sepay',
      paymentId: transactionContent, // Used for matching
      referredBy: discountMetadata.referrerId,
      discountAmount: originalAmount - finalAmount,
      metadata: JSON.stringify({
        ...discountMetadata,
        githubUsername: data.githubUsername,
        vatInvoiceRequested: data.vatInvoiceRequested,
        encryptedTaxId,
      }),
    }).returning();

    // 7. Generate payment instructions
    const qrCode = generateVietQRUrl(
      process.env.SEPAY_ACCOUNT_NUMBER!,
      process.env.SEPAY_BANK_NAME!,
      finalAmount,
      transactionContent
    );

    return NextResponse.json({
      orderId: order[0].id,
      paymentMethod: 'bank_transfer',
      payment: {
        bankName: process.env.SEPAY_BANK_NAME,
        accountNumber: process.env.SEPAY_ACCOUNT_NUMBER,
        accountName: process.env.SEPAY_ACCOUNT_NAME,
        amount: finalAmount,
        currency: 'VND',
        content: transactionContent,
        qrCode,
        instructions: [
          'Open your banking app',
          'Scan the QR code or transfer manually',
          'Use the exact transfer content shown',
          'Payment will be confirmed automatically',
        ],
      },
      statusCheckUrl: `/api/orders/${order[0].id}/status`,
    });

  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json({ error: error.errors }, { status: 400 });
    }
    console.error('SePay checkout error:', error);
    return NextResponse.json(
      { error: 'Failed to create checkout' },
      { status: 500 }
    );
  }
}
```

## Webhook Handling

### Webhook Authentication (Timing-Safe)
```typescript
// app/api/webhooks/sepay/route.ts
import { timingSafeEqual } from 'crypto';
import { NextResponse } from 'next/server';

function verifyWebhookAuth(request: Request): boolean {
  const authHeader = request.headers.get('Authorization');
  if (!authHeader) return false;

  const expectedKey = process.env.SEPAY_WEBHOOK_API_KEY!;

  // Support both "Bearer" and "Apikey" formats
  let providedKey: string;
  if (authHeader.startsWith('Bearer ')) {
    providedKey = authHeader.slice(7);
  } else if (authHeader.startsWith('Apikey ')) {
    providedKey = authHeader.slice(7);
  } else {
    return false;
  }

  // Timing-safe comparison to prevent timing attacks
  try {
    const expected = Buffer.from(expectedKey);
    const provided = Buffer.from(providedKey);
    if (expected.length !== provided.length) return false;
    return timingSafeEqual(expected, provided);
  } catch {
    return false;
  }
}

export async function POST(request: Request) {
  // 1. Verify authentication
  if (!verifyWebhookAuth(request)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const payload = await request.json();

  // 2. Extract event ID for idempotency
  const eventId = String(payload.id || payload.transaction_id || Date.now());

  // 3. Check for duplicate
  const existingEvent = await db.select()
    .from(webhookEvents)
    .where(eq(webhookEvents.eventId, eventId))
    .limit(1);

  if (existingEvent.length > 0) {
    console.log(`Duplicate SePay webhook ignored: ${eventId}`);
    return NextResponse.json({ success: true });
  }

  // 4. Record event BEFORE processing (idempotency)
  await db.insert(webhookEvents).values({
    id: crypto.randomUUID(),
    provider: 'sepay',
    eventType: 'transaction',
    eventId,
    payload: JSON.stringify(payload),
    processed: false,
  });

  try {
    await processTransaction(payload);

    await db.update(webhookEvents)
      .set({ processed: true, processedAt: new Date() })
      .where(eq(webhookEvents.eventId, eventId));

  } catch (error) {
    // Log error but return 200 to prevent retry loop
    await db.update(webhookEvents)
      .set({
        processed: true,
        processedAt: new Date(),
        error: error instanceof Error ? error.message : 'Unknown error',
      })
      .where(eq(webhookEvents.eventId, eventId));
  }

  // Always return 200 to prevent SePay retries
  return NextResponse.json({ success: true });
}
```

### Webhook Payload Structure
```typescript
interface SepayWebhookPayload {
  id: number;                    // Transaction ID (unique key)
  gateway: string;               // Bank name (e.g., "Vietcombank")
  transactionDate: string;       // "2025-01-07 10:30:00"
  accountNumber: string;         // Account number
  code?: string;                 // Optional payment code
  content: string;               // Transaction memo - CRITICAL for matching
  transferType: 'in' | 'out';    // Only process 'in'
  transferAmount: number;        // Amount in VND
  accumulated: number;           // Balance after transaction
  subAccount?: string;
  referenceCode?: string;
  description?: string;
}
```

## Order Matching Strategy

### Multi-Strategy Fallback Chain
```typescript
// lib/sepay.ts
export async function findOrderByTransaction(
  payload: SepayWebhookPayload
): Promise<{ order: Order | null; matchMethod: string }> {
  const { content, transferAmount, transactionDate } = payload;

  // Strategy 1: Parse Order ID from content (preferred)
  const parsedOrderId = parseOrderIdFromContent(content);
  if (parsedOrderId) {
    const order = await db.select()
      .from(orders)
      .where(eq(orders.id, parsedOrderId))
      .limit(1);

    if (order[0]) {
      return { order: order[0], matchMethod: 'content-parse' };
    }
  }

  // Strategy 2: Team payment ID match
  const teamMatch = content.match(/TEAM([A-F0-9]{8})/i);
  if (teamMatch) {
    const teamPaymentId = `TEAM${teamMatch[1].toUpperCase()}`;
    const order = await db.select()
      .from(orders)
      .where(eq(orders.paymentId, teamPaymentId))
      .limit(1);

    if (order[0]) {
      return { order: order[0], matchMethod: 'team-payment-id' };
    }
  }

  // Strategy 3: Amount + timestamp window (±30 minutes)
  const transactionTime = new Date(transactionDate);
  const windowStart = new Date(transactionTime.getTime() - 30 * 60 * 1000);
  const windowEnd = new Date(transactionTime.getTime() + 30 * 60 * 1000);

  const windowMatches = await db.select()
    .from(orders)
    .where(and(
      eq(orders.status, 'pending'),
      eq(orders.paymentProvider, 'sepay'),
      eq(orders.amount, transferAmount),
      gte(orders.createdAt, windowStart),
      lte(orders.createdAt, windowEnd)
    ))
    .limit(10);

  if (windowMatches.length === 1) {
    return { order: windowMatches[0], matchMethod: 'timestamp-window' };
  }

  if (windowMatches.length > 1) {
    // Multiple matches - select closest by creation time
    const closest = windowMatches.reduce((prev, curr) => {
      const prevDiff = Math.abs(prev.createdAt.getTime() - transactionTime.getTime());
      const currDiff = Math.abs(curr.createdAt.getTime() - transactionTime.getTime());
      return currDiff < prevDiff ? curr : prev;
    });
    return { order: closest, matchMethod: 'timestamp-window-closest' };
  }

  // Strategy 4: Amount only (last resort - single match only)
  const amountMatches = await db.select()
    .from(orders)
    .where(and(
      eq(orders.status, 'pending'),
      eq(orders.paymentProvider, 'sepay'),
      eq(orders.amount, transferAmount)
    ))
    .limit(2);

  if (amountMatches.length === 1) {
    console.warn(`⚠️ Amount-only match for ${transferAmount} VND - verify manually`);
    return { order: amountMatches[0], matchMethod: 'amount-only' };
  }

  // No match found
  console.error(`❌ Could not match order:
    Content: "${content}"
    Amount: ${transferAmount} VND
    Transaction Date: ${transactionDate}`);

  return { order: null, matchMethod: 'none' };
}
```

### UUID Parsing with Bank Transformations
```typescript
// lib/sepay.ts
export function parseOrderIdFromContent(content: string): string | null {
  if (!content) return null;

  // Pattern 1: Standard "ORDER {uuid}"
  const orderMatch = content.match(/ORDER\s+([\w-]+)/i);
  if (orderMatch) {
    return normalizeUUID(orderMatch[1]);
  }

  // Pattern 2: UUID anywhere in content (banks may strip/transform content)
  // Match 8-4-4-4-12 hex with optional dashes
  const uuidMatch = content.match(
    /([0-9A-F]{8}-?[0-9A-F]{4}-?[0-9A-F]{4}-?[0-9A-F]{4}-?[0-9A-F]{12})/i
  );
  if (uuidMatch) {
    return normalizeUUID(uuidMatch[1]);
  }

  return null;
}

function normalizeUUID(input: string): string | null {
  // Remove dashes and validate
  const cleaned = input.replace(/-/g, '');

  if (cleaned.length !== 32) return null;
  if (!/^[0-9a-f]+$/i.test(cleaned)) return null;

  // Re-format to standard UUID format
  return [
    cleaned.slice(0, 8),
    cleaned.slice(8, 12),
    cleaned.slice(12, 16),
    cleaned.slice(16, 20),
    cleaned.slice(20),
  ].join('-').toLowerCase();
}
```

### Handled Content Formats
```
ORDER 4e4635f4-0478-4080-a5c5-48da91f97f1e     ✅ Standard
ORDER 4e4635f404784080a5c548da91f97f1e         ✅ Bank stripped dashes
ORDER4e4635f404784080a5c548da91f97f1e          ✅ No space
4e4635f404784080a5c548da91f97f1e-ORDER         ✅ Reversed
order 4e4635f4-0478-4080-a5c5-48da91f97f1e    ✅ Lowercase
BankAPINotify 4e4635f404784080a5c548da91f97f1e... ✅ Extra prefix
4e4635f404784080a5c548da91f97f1e                   ✅ UUID only
```

## Transaction Processing

### Complete Processing Flow
```typescript
async function processTransaction(payload: SepayWebhookPayload) {
  // 1. Only process incoming transfers
  if (payload.transferType !== 'in') {
    console.log('Skipping outbound transfer');
    return;
  }

  // 2. Find matching order
  const { order, matchMethod } = await findOrderByTransaction(payload);
  if (!order) {
    console.error('No matching order found');
    return;
  }

  // 3. Verify amount (allow overpayment)
  if (payload.transferAmount < order.amount) {
    console.error(`Underpayment: expected ${order.amount}, got ${payload.transferAmount}`);
    return;
  }
  if (payload.transferAmount > order.amount) {
    console.log(`Overpayment accepted: expected ${order.amount}, got ${payload.transferAmount}`);
  }

  // 4. Update order with transaction details
  const existingMetadata = order.metadata ? JSON.parse(order.metadata) : {};
  await db.update(orders)
    .set({
      status: 'completed',
      paymentId: String(payload.id),
      metadata: JSON.stringify({
        ...existingMetadata, // Preserve discount info
        gateway: payload.gateway,
        transactionDate: payload.transactionDate,
        accountNumber: payload.accountNumber,
        transferAmount: payload.transferAmount,
        content: payload.content,
        matchMethod,
        transactionId: payload.id,
      }),
      updatedAt: new Date(),
    })
    .where(eq(orders.id, order.id));

  // 5. Create license (non-blocking)
  try {
    await createLicense(order);
  } catch (error) {
    console.error('Failed to create license:', error);
  }

  // 6. Send confirmation email (non-blocking)
  try {
    await sendOrderConfirmation(order, payload);
  } catch (error) {
    console.error('Failed to send confirmation:', error);
  }

  // 7. Create referral commission (non-blocking)
  if (order.referredBy) {
    try {
      // Commission based on actual paid amount
      await createCommission({
        orderId: order.id,
        referrerId: order.referredBy,
        baseAmount: payload.transferAmount, // Actual paid amount
        currency: 'VND',
      });
    } catch (error) {
      console.error('Failed to create commission:', error);
    }
  }

  // 8. Update referrer tier (non-blocking)
  if (order.referredBy) {
    try {
      const usdConversion = await convertVndToUsd(payload.transferAmount);
      await updateReferrerTier(order.referredBy, usdConversion.usdCents, order.id);
    } catch (error) {
      console.error('Failed to update tier:', error);
    }
  }

  // 9. Grant GitHub access (non-blocking)
  try {
    const metadata = JSON.parse(order.metadata || '{}');
    await inviteToGitHub(metadata.githubUsername, order.productType);
  } catch (error) {
    console.error('Failed to invite to GitHub:', error);
  }

  // 10. Sync Polar discount redemption (non-blocking)
  const metadata = JSON.parse(order.metadata || '{}');
  if (metadata.couponId && metadata.couponCode) {
    try {
      await syncPolarDiscountWithRetry(order.id, metadata.couponId, metadata.couponCode);
    } catch (error) {
      console.error('Failed to sync Polar discount:', error);
      await sendDiscordAlert('Polar discount sync failed', { orderId: order.id });
    }
  }

  // 11. Send sales notification (non-blocking)
  try {
    await sendSalesNotification({
      ...order,
      gateway: payload.gateway,
      transactionId: payload.id,
    });
  } catch (error) {
    console.error('Failed to send Discord notification:', error);
  }
}
```

## Currency Conversion

### VND to USD with Multi-Layer Fallback
```typescript
// lib/currency.ts
const EXCHANGE_RATE_CACHE_TTL = 60 * 60 * 1000; // 1 hour
const FALLBACK_VND_TO_USD = 24500; // Conservative fallback

let exchangeRateCache: {
  rate: number;
  timestamp: number;
  source: 'api' | 'cached' | 'expired' | 'fallback';
} | null = null;

export async function convertVndToUsd(vndAmount: number): Promise<{
  usdCents: number;
  rate: number;
  source: string;
}> {
  const now = Date.now();

  // Layer 1: Fresh cache
  if (exchangeRateCache && now - exchangeRateCache.timestamp < EXCHANGE_RATE_CACHE_TTL) {
    const usdCents = Math.round((vndAmount / exchangeRateCache.rate) * 100);
    return { usdCents, rate: exchangeRateCache.rate, source: 'cached' };
  }

  // Layer 2: Try live API
  try {
    const response = await fetch(
      'https://api.exchangerate-api.com/v4/latest/USD',
      { signal: AbortSignal.timeout(5000) }
    );
    const data = await response.json();
    const rate = data.rates.VND;

    exchangeRateCache = { rate, timestamp: now, source: 'api' };
    const usdCents = Math.round((vndAmount / rate) * 100);
    return { usdCents, rate, source: 'api' };

  } catch (error) {
    console.warn('Exchange rate API failed:', error);

    // Layer 3: Expired cache (better than nothing)
    if (exchangeRateCache) {
      const usdCents = Math.round((vndAmount / exchangeRateCache.rate) * 100);
      return { usdCents, rate: exchangeRateCache.rate, source: 'expired_cache' };
    }

    // Layer 4: Hardcoded fallback
    const usdCents = Math.round((vndAmount / FALLBACK_VND_TO_USD) * 100);
    return { usdCents, rate: FALLBACK_VND_TO_USD, source: 'fallback' };
  }
}
```

### USD Discount to VND
```typescript
// When Polar discount is in USD, convert to VND for SePay checkout
export function convertUsdDiscountToVnd(
  discount: { type: 'fixed' | 'percentage'; amount?: number; basisPoints?: number },
  amountVND: number
): number {
  if (discount.type === 'percentage') {
    // Basis points: 1000 = 10%, 10000 = 100%
    const percentage = (discount.basisPoints || 0) / 10000;
    return Math.round(amountVND * percentage);
  } else {
    // Fixed amount in USD cents → VND
    const usdDollars = (discount.amount || 0) / 100;
    return Math.round(usdDollars * 24500); // Use conservative rate
  }
}
```

## Invoice Email Template

### HTML Invoice Generation
```typescript
// lib/emails/sepay-invoice.ts
export function generateSepayInvoice(order: Order, transaction: TransactionInfo): string {
  const metadata = JSON.parse(order.metadata || '{}');
  const invoiceNumber = `INV-${format(new Date(), 'yyyyMMdd')}-${order.id.slice(-8).toUpperCase()}`;

  // Format VND with Vietnamese locale
  const formatVND = (amount: number) =>
    new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);

  // Escape HTML to prevent XSS
  const escapeHtml = (text: string) =>
    text.replace(/[&<>"']/g, char => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    })[char] || char);

  return `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        .invoice { font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #ff6b6b, #feca57); padding: 20px; }
        .status { background: #10b981; color: white; padding: 4px 12px; border-radius: 4px; }
        .amount { font-size: 24px; font-weight: bold; }
        .savings { color: #10b981; }
      </style>
    </head>
    <body>
      <div class="invoice">
        <div class="header">
          <h1>Invoice</h1>
          <span class="status">PAID</span>
        </div>

        <table>
          <tr><td>Invoice #:</td><td>${invoiceNumber}</td></tr>
          <tr><td>Customer:</td><td>${escapeHtml(metadata.name || order.email)}</td></tr>
          <tr><td>Email:</td><td>${escapeHtml(order.email)}</td></tr>
          <tr><td>Payment Date:</td><td>${format(new Date(transaction.transactionDate), 'dd/MM/yyyy HH:mm')}</td></tr>
          <tr><td>Transaction Ref:</td><td>${transaction.transactionId || 'N/A'}</td></tr>
        </table>

        <h3>Order Details</h3>
        <table>
          <tr><td>Product:</td><td>${getProductName(order.productType)}</td></tr>
          <tr><td>Original Price:</td><td>${formatVND(metadata.originalAmount || order.amount)}</td></tr>
          ${metadata.couponDiscountAmount ? `
            <tr><td>Coupon (${metadata.couponCode}):</td><td>-${formatVND(metadata.couponDiscountAmount)}</td></tr>
          ` : ''}
          ${metadata.referralDiscountAmount ? `
            <tr><td>Referral Discount (20%):</td><td>-${formatVND(metadata.referralDiscountAmount)}</td></tr>
          ` : ''}
          ${order.discountAmount > 0 ? `
            <tr class="savings"><td>Total Savings:</td><td>-${formatVND(order.discountAmount)}</td></tr>
          ` : ''}
          <tr class="amount"><td>Total Paid:</td><td>${formatVND(order.amount)}</td></tr>
        </table>

        <p>Thank you for your purchase!</p>
        <p>Support: support@example.com</p>
      </div>
    </body>
    </html>
  `;
}
```

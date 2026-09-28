## Error Handling Patterns

### Always Return 200 to SePay
```typescript
// Webhook must always return 200 to prevent retry loop
export async function POST(request: Request) {
  try {
    // ... processing
  } catch (error) {
    // Log error but don't fail
    console.error('Webhook processing error:', error);
    await logWebhookError(error);
  }

  // ALWAYS return 200
  return NextResponse.json({ success: true });
}
```

### Non-Blocking Post-Payment Operations
```typescript
// Wrap each operation in try-catch
const operations = [
  { name: 'License', fn: () => createLicense(order) },
  { name: 'Email', fn: () => sendOrderConfirmation(order) },
  { name: 'Commission', fn: () => createCommission(order) },
  { name: 'GitHub', fn: () => inviteToGitHub(username, productType) },
  { name: 'Discord', fn: () => sendSalesNotification(order) },
];

for (const op of operations) {
  try {
    await op.fn();
    console.log(`✅ ${op.name} completed`);
  } catch (error) {
    console.error(`❌ ${op.name} failed:`, error);
    // Continue - don't block other operations
  }
}
```

### Amount Validation
```typescript
// Reject underpayment, accept overpayment
if (transferAmount < order.amount) {
  console.error(`Underpayment: expected ${order.amount}, received ${transferAmount}`);
  await flagOrderForReview(order.id, 'underpayment');
  return; // Don't process
}

if (transferAmount > order.amount) {
  console.log(`Overpayment: expected ${order.amount}, received ${transferAmount}`);
  // Continue processing - customer paid more than required
}
```

## Testing Patterns

### Unit Tests for UUID Parsing
```typescript
// __tests__/lib/sepay.test.ts
describe('parseOrderIdFromContent', () => {
  it('parses standard format', () => {
    expect(parseOrderIdFromContent('ORDER 4e4635f4-0478-4080-a5c5-48da91f97f1e'))
      .toBe('4e4635f4-0478-4080-a5c5-48da91f97f1e');
  });

  it('handles bank dash-stripping', () => {
    expect(parseOrderIdFromContent('ORDER 4e4635f404784080a5c548da91f97f1e'))
      .toBe('4e4635f4-0478-4080-a5c5-48da91f97f1e');
  });

  it('handles real-world Vietnamese bank memo', () => {
    expect(parseOrderIdFromContent('BankAPINotify 4e4635f404784080a5c548da91f97f1e-CHUYEN TIEN'))
      .toBe('4e4635f4-0478-4080-a5c5-48da91f97f1e');
  });

  it('returns null for invalid content', () => {
    expect(parseOrderIdFromContent('ORDER')).toBeNull();
    expect(parseOrderIdFromContent('4e4635f4-0478')).toBeNull();
    expect(parseOrderIdFromContent('104588021672-ORDER')).toBeNull();
  });
});
```

### Webhook Integration Test Script
```bash
#!/bin/bash
# scripts/test-sepay-webhook.sh

BASE_URL="http://localhost:3000/api/webhooks/sepay"
API_KEY="your-test-key"

# Test 1: Valid Bearer token
echo "Test 1: Bearer token auth"
curl -X POST "$BASE_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"id":12345,"content":"ORDER test-uuid","transferAmount":2450000,"transferType":"in"}'

# Test 2: Valid Apikey format
echo "Test 2: Apikey auth"
curl -X POST "$BASE_URL" \
  -H "Authorization: Apikey $API_KEY" \
  -d '{"id":12346,"content":"ORDER test-uuid","transferAmount":2450000,"transferType":"in"}'

# Test 3: Missing auth (should return 401)
echo "Test 3: No auth (expect 401)"
curl -X POST "$BASE_URL" \
  -d '{"id":12347,"content":"test","transferAmount":100000,"transferType":"in"}'

# Test 4: Invalid key (should return 401)
echo "Test 4: Invalid key (expect 401)"
curl -X POST "$BASE_URL" \
  -H "Authorization: Bearer wrong-key" \
  -d '{"id":12348,"content":"test","transferAmount":100000,"transferType":"in"}'
```

## Database Schema

### Orders Table Extensions for SePay
```typescript
// Fields used specifically for SePay
{
  paymentId: text('payment_id'),      // Transaction content or TEAM{8} code
  paymentProvider: literal('sepay'),  // Distinguishes from Polar
  currency: literal('VND'),           // Always VND for SePay
  amount: integer('amount'),          // In VND (no decimals)
}

// Metadata JSON includes:
{
  gateway: string,           // Bank name from webhook
  transactionDate: string,   // Webhook timestamp
  transactionId: number,     // SePay transaction ID
  transferAmount: number,    // Actual received amount
  matchMethod: string,       // How order was matched
  content: string,           // Original transaction memo
  encryptedTaxId?: string,   // For VAT invoices
}
```

### Recommended Indexes
```sql
CREATE INDEX idx_orders_sepay_pending ON orders (status, payment_provider, amount)
  WHERE status = 'pending' AND payment_provider = 'sepay';

CREATE INDEX idx_orders_sepay_timestamp ON orders (created_at)
  WHERE payment_provider = 'sepay';

CREATE INDEX idx_orders_payment_id ON orders (payment_id)
  WHERE payment_provider = 'sepay';
```

## Production Checklist

- [ ] Environment variables configured
- [ ] Bank account verified and active
- [ ] Webhook endpoint publicly accessible (HTTPS)
- [ ] Webhook API key set and verified
- [ ] Timing-safe auth comparison implemented
- [ ] Idempotency handling tested with duplicate webhooks
- [ ] UUID parsing tested with real Vietnamese bank memos
- [ ] Amount validation (underpayment rejection) tested
- [ ] Overpayment handling verified
- [ ] Currency conversion fallback chain tested
- [ ] Invoice email template tested
- [ ] Error monitoring enabled
- [ ] Structured logging in place
- [ ] Database indexes created
- [ ] Polar discount sync tested (for shared coupons)
- [ ] Team payment ID format tested
- [ ] Non-blocking operations wrapped in try-catch
- [ ] Always-200 webhook response verified

## Common Pitfalls

1. **Not handling bank dash-stripping** - Banks may remove dashes from UUIDs
2. **Rejecting overpayments** - Should accept; customer paid more
3. **Blocking webhook on non-critical failures** - Wrap in try-catch, continue
4. **Not using timing-safe comparison** - Vulnerable to timing attacks
5. **Returning non-200 on error** - Causes SePay retry loops
6. **Using raw exchange rates without fallback** - API can fail
7. **Applying discounts in wrong order** - Always coupon first, then referral
8. **Not logging matchMethod** - Hard to debug failed matches
9. **Not preserving checkout metadata** - Lose discount audit trail
10. **Synchronous Polar discount sync** - Can fail; use retry with backoff
11. **Case-sensitive content matching** - Banks may uppercase/lowercase
12. **Missing amount-only match safety** - Reject ambiguous matches

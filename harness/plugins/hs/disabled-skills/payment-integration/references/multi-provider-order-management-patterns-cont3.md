# Multi-Provider Order Management Patterns (continued 4/4)

## Admin Order Management API

### Order Listing with Provider Info
```typescript
// app/api/admin/orders/route.ts
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const page = parseInt(searchParams.get('page') || '1');
  const limit = parseInt(searchParams.get('limit') || '50');
  const provider = searchParams.get('provider'); // 'polar' | 'sepay' | null
  const status = searchParams.get('status');

  let query = db.select()
    .from(orders)
    .orderBy(desc(orders.createdAt));

  if (provider) {
    query = query.where(eq(orders.paymentProvider, provider));
  }
  if (status) {
    query = query.where(eq(orders.status, status));
  }

  const results = await query
    .limit(limit)
    .offset((page - 1) * limit);

  // Normalize amounts to USD for display
  const ordersWithNormalized = await Promise.all(
    results.map(async (order) => {
      const normalized = await normalizeOrderToUsd(order);
      return {
        ...order,
        amountUsdCents: normalized.amountUsdCents,
        displayAmount: order.currency === 'VND'
          ? formatVND(order.amount)
          : formatUSD(order.amount),
      };
    })
  );

  return NextResponse.json({
    orders: ordersWithNormalized,
    pagination: {
      page,
      limit,
      hasMore: results.length === limit,
    },
  });
}
```

## Best Practices Summary

### 1. Currency Handling
- Store amounts in original currency (USD or VND)
- Always store currency code with amount
- Use multi-layer fallback for exchange rates
- Convert to USD for reporting/comparison

### 2. Order Management
- Use unified orders table for both providers
- Store provider-specific data in metadata JSON
- Normalize to USD for tier calculations

### 3. Commission System
- Store original currency and USD equivalent
- Calculate tier based on USD values
- Handle currency conversion in commission creation

### 4. Webhook Processing
- Use idempotency keys for deduplication
- Record event before processing
- Always return 200 to prevent retry loops
- Log errors in event record for debugging

### 5. Cross-Provider Sync
- Sync discount redemptions from SePay to Polar
- Use retry with exponential backoff
- Mark orders as synced to prevent duplicates

### 6. Refund Handling
- Check order status before processing
- Cancel related commissions
- Recalculate referrer tier after cancellation
- Optionally keep access (goodwill refunds)

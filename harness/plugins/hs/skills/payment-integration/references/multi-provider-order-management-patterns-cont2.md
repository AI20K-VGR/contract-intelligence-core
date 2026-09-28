# Multi-Provider Order Management Patterns (continued 3/4)

## Refund Handling

### Unified Refund Flow
```typescript
// lib/refunds.ts
export async function processRefund(
  orderId: string,
  options: { keepAccess?: boolean; reason?: string }
): Promise<{ success: boolean; error?: string }> {
  const order = await db.select()
    .from(orders)
    .where(eq(orders.id, orderId))
    .limit(1);

  if (!order[0]) {
    return { success: false, error: 'Order not found' };
  }

  if (order[0].status !== 'completed') {
    return { success: false, error: 'Order not refundable' };
  }

  try {
    // 1. Process refund with payment provider
    if (order[0].paymentProvider === 'polar') {
      await polar.orders.refund({ id: order[0].paymentId! });
    } else {
      // SePay: Manual bank transfer refund required
      // Just mark order, admin handles bank transfer
      console.log(`Manual refund needed for SePay order ${orderId}`);
    }

    // 2. Update order status
    await db.update(orders)
      .set({
        status: 'refunded',
        metadata: JSON.stringify({
          ...JSON.parse(order[0].metadata || '{}'),
          refundedAt: new Date().toISOString(),
          refundReason: options.reason,
          keepAccess: options.keepAccess,
        }),
        updatedAt: new Date(),
      })
      .where(eq(orders.id, orderId));

    // 3. Cancel commission (if any)
    if (order[0].referredBy) {
      await db.update(commissions)
        .set({
          status: 'cancelled',
          cancelledAt: new Date(),
        })
        .where(eq(commissions.orderId, orderId));

      // Recalculate referrer tier
      await recalculateReferrerTier(order[0].referredBy);
    }

    // 4. Revoke access (unless keepAccess)
    if (!options.keepAccess) {
      const metadata = JSON.parse(order[0].metadata || '{}');
      if (metadata.githubUsername) {
        await revokeGitHubAccess(metadata.githubUsername, order[0].productType);
      }

      await db.update(licenses)
        .set({ isActive: false, revokedAt: new Date() })
        .where(eq(licenses.orderId, orderId));
    }

    return { success: true };

  } catch (error) {
    console.error('Refund failed:', error);
    return { success: false, error: error instanceof Error ? error.message : 'Refund failed' };
  }
}
```

## Webhook Event Tracking

### Unified Webhook Events Table
```typescript
// db/schema/webhook-events.ts
export const webhookEvents = pgTable('webhook_events', {
  id: uuid('id').primaryKey().defaultRandom(),
  provider: text('provider').notNull(),          // 'polar' or 'sepay'
  eventType: text('event_type').notNull(),       // Event type/name
  eventId: text('event_id').notNull().unique(),  // Idempotency key
  payload: text('payload').notNull(),            // Raw JSON payload
  processed: boolean('processed').default(false),
  processedAt: timestamp('processed_at'),
  error: text('error'),                          // Error message if failed
  createdAt: timestamp('created_at').defaultNow(),
});

// Partial index for unprocessed events
// CREATE INDEX idx_webhook_events_unprocessed ON webhook_events (created_at)
//   WHERE processed = false;
```

### Idempotent Webhook Processing
```typescript
// lib/webhooks.ts
export async function processWebhookIdempotently<T>(
  provider: 'polar' | 'sepay',
  eventId: string,
  eventType: string,
  payload: string,
  handler: () => Promise<T>
): Promise<{ processed: boolean; result?: T; error?: string }> {
  // Check for duplicate
  const existing = await db.select()
    .from(webhookEvents)
    .where(eq(webhookEvents.eventId, eventId))
    .limit(1);

  if (existing.length > 0) {
    return { processed: false }; // Already processed
  }

  // Record event BEFORE processing
  await db.insert(webhookEvents).values({
    id: crypto.randomUUID(),
    provider,
    eventType,
    eventId,
    payload,
    processed: false,
  });

  try {
    const result = await handler();

    await db.update(webhookEvents)
      .set({ processed: true, processedAt: new Date() })
      .where(eq(webhookEvents.eventId, eventId));

    return { processed: true, result };

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';

    await db.update(webhookEvents)
      .set({
        processed: true,
        processedAt: new Date(),
        error: errorMessage,
      })
      .where(eq(webhookEvents.eventId, eventId));

    return { processed: true, error: errorMessage };
  }
}
```

## Discount Cross-Provider Sync

### Syncing SePay Usage to Polar
```typescript
// lib/polar-discount-sync.ts
// When a Polar discount is used via SePay, decrement Polar's redemption count

export async function syncDiscountRedemptionToPolar(
  orderId: string,
  discountId: string,
  discountCode: string
): Promise<{ success: boolean; action: string }> {
  const order = await db.select()
    .from(orders)
    .where(eq(orders.id, orderId))
    .limit(1);

  if (!order[0]) {
    return { success: false, action: 'order_not_found' };
  }

  const metadata = order[0].metadata ? JSON.parse(order[0].metadata) : {};

  // Idempotency check
  if (metadata.polarDiscountSynced) {
    return { success: true, action: 'already_synced' };
  }

  const polar = getPolar();

  try {
    const discount = await polar.discounts.get({ id: discountId });

    // Skip if unlimited redemptions
    if (discount.maxRedemptions === null) {
      await markSynced(orderId, 'skipped_unlimited');
      return { success: true, action: 'skipped_unlimited' };
    }

    const currentMax = discount.maxRedemptions;

    if (currentMax <= 1) {
      // Delete discount if this was last use
      await polar.discounts.delete({ id: discountId });
      await markSynced(orderId, 'deleted');
      return { success: true, action: 'deleted' };
    } else {
      // Decrement max redemptions
      await polar.discounts.update({
        id: discountId,
        discountUpdate: { maxRedemptions: currentMax - 1 },
      });
      await markSynced(orderId, 'decremented');
      return { success: true, action: 'decremented' };
    }

  } catch (error: any) {
    if (error.statusCode === 404) {
      await markSynced(orderId, 'already_deleted');
      return { success: true, action: 'already_deleted' };
    }
    throw error;
  }
}

async function markSynced(orderId: string, action: string) {
  const order = await db.select().from(orders).where(eq(orders.id, orderId)).limit(1);
  const metadata = order[0].metadata ? JSON.parse(order[0].metadata) : {};

  await db.update(orders)
    .set({
      metadata: JSON.stringify({
        ...metadata,
        polarDiscountSynced: true,
        polarDiscountSyncAction: action,
        polarDiscountSyncedAt: new Date().toISOString(),
      }),
    })
    .where(eq(orders.id, orderId));
}

// Retry wrapper with exponential backoff
export async function syncWithRetry(
  orderId: string,
  discountId: string,
  discountCode: string,
  attempt: number = 1
): Promise<{ success: boolean; action: string }> {
  const MAX_ATTEMPTS = 3;

  try {
    return await syncDiscountRedemptionToPolar(orderId, discountId, discountCode);
  } catch (error) {
    if (attempt < MAX_ATTEMPTS) {
      const delay = Math.pow(2, attempt) * 1000; // 2s, 4s
      await sleep(delay);
      return syncWithRetry(orderId, discountId, discountCode, attempt + 1);
    }
    throw error;
  }
}
```


---

Continued in [multi-provider-order-management-patterns-cont3.md](multi-provider-order-management-patterns-cont3.md)

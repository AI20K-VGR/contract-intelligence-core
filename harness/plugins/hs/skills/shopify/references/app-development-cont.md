# App Development Reference (continued 2/2)

## Rate Limiting

GraphQL Admin API uses a cost model:
- Single-query requested cost must not exceed 1000.
- Response extensions: requested cost, actual cost, throttle status.
- Restore rates are plan-dependent; do not hardcode one global budget.

```javascript
async function graphqlWithRetry(shop, token, apiVersion, query, variables = {}) {
  const result = await graphqlRequest(shop, token, apiVersion, query, variables);
  const cost = result.extensions?.cost;

  if (cost?.throttleStatus) {
    const { currentlyAvailable, restoreRate } = cost.throttleStatus;
    if (currentlyAvailable < cost.requestedQueryCost) {
      const missing = cost.requestedQueryCost - currentlyAvailable;
      const waitMs = Math.ceil((missing / restoreRate) * 1000);
      await sleep(waitMs);
    }
  }

  return result.data;
}
```

Use requested vs actual cost to tune field selection and page sizes.

## Best Practices

**Security:** authenticate via the official app libraries (managed install + session tokens + token exchange), store tokens encrypted, verify webhook HMACs from raw bodies, and never expose access tokens in browser code.

**Performance:** pagination, bulk operations for large jobs, query only needed fields.

**Reliability:** retry only when throttle status indicates capacity will restore; handle webhook redelivery idempotently.

**Compliance:** subscribe to privacy compliance topics, minimize customer/order data logs.

## Resources

- App Development: https://shopify.dev/docs/apps
- GraphQL Admin API: https://shopify.dev/docs/api/admin-graphql
- Authentication & authorization: https://shopify.dev/docs/apps/build/authentication-authorization
- Webhooks: https://shopify.dev/docs/apps/build/webhooks
- Billing API: https://shopify.dev/docs/apps/launch/billing
- Admin API rate limits: https://shopify.dev/docs/api/usage/rate-limits

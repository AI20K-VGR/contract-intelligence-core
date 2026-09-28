# App Development Reference

Guide: building Shopify apps — GraphQL Admin API, webhooks, billing, metafields, current Shopify CLI app config workflows.

GraphQL Admin API is the default for new apps. REST Admin API is legacy/migration-only; avoid REST examples for new development unless maintaining an existing integration.

## Authentication

New embedded apps use Shopify-managed installation, session tokens, and token exchange via the official app libraries (`@shopify/shopify-app-react-router`, `@shopify/shopify-app-remix`, or `@shopify/shopify-api`). Do not hand-roll the legacy authorization-code-grant OAuth flow for new apps.

See `references/embedded-apps.md`: managed install, App Bridge v4, session-token auth, token exchange, official libraries, expiring offline-token deadlines (2026-04-01 / 2027-01-01).

## App Configuration Workflow

```bash
shopify app init
shopify app config link
shopify app config use
shopify app dev
shopify app deploy
```

Notes:
- `shopify app config link` connects local config to an existing app.
- `shopify app config use` selects the active config for development/deploy.
- Named config files may use `shopify.app.{config}.toml`.
- `shopify app dev` applies the selected config to the development store.
- Production/global Shopify app config and extension changes require `shopify app deploy`.
- `shopify app deploy` releases Shopify-managed config/extensions only. Deploy hosted web app code separately.
- `shopify app config push` is historical/obsolete wording; do not recommend it in new workflows.

## GraphQL Admin API

Use `{api_version}` in reusable snippets. Latest stable as of 2026-06-12 is `2026-04`; review API versions quarterly, verify current mutation signatures before updates.

```javascript
async function graphqlRequest(shop, accessToken, apiVersion, query, variables = {}) {
  const response = await fetch(
    `https://${shop}/admin/api/${apiVersion}/graphql.json`,
    {
      method: 'POST',
      headers: {
        'X-Shopify-Access-Token': accessToken,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query, variables }),
    }
  );

  const body = await response.json();
  if (body.errors) throw new Error(`GraphQL errors: ${JSON.stringify(body.errors)}`);
  return body;
}
```

Check `X-Shopify-API-Version` in responses to detect fall-forward behavior.

### Product Operations

**Create Product:**

```graphql
mutation CreateProduct($product: ProductCreateInput!, $media: [CreateMediaInput!]) {
  productCreate(product: $product, media: $media) {
    product { id title handle }
    userErrors { field message }
  }
}
```

Variables:

```json
{
  "product": {
    "title": "New Product",
    "productType": "Apparel",
    "vendor": "Brand",
    "status": "ACTIVE"
  },
  "media": [
    {
      "mediaContentType": "IMAGE",
      "originalSource": "https://example.com/product.jpg",
      "alt": "New Product"
    }
  ]
}
```

**Update Product:**

```graphql
mutation UpdateProduct($product: ProductUpdateInput!, $identifier: ProductIdentifierInput) {
  productUpdate(product: $product, identifier: $identifier) {
    product { id title }
    userErrors { field message }
  }
}
```

**Create Variants After Options Exist:**

```graphql
mutation CreateVariants($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkCreate(productId: $productId, variants: $variants) {
    productVariants { id title }
    userErrors { field message }
  }
}
```

Create product options first, then use `productVariantsBulkCreate` for additional variants. Do not rely on old product input shapes that mixed initial variant fields into product creation.

## Webhooks

### Configuration

In `shopify.app.toml`:

```toml
[webhooks]
api_version = "2026-04"

[[webhooks.subscriptions]]
topics = ["orders/create"]
uri = "/webhooks/orders/create"

[[webhooks.subscriptions]]
topics = ["products/update"]
uri = "/webhooks/products/update"

[[webhooks.subscriptions]]
topics = ["app/uninstalled"]
uri = "/webhooks/app/uninstalled"

[[webhooks.subscriptions]]
compliance_topics = ["customers/data_request", "customers/redact", "shop/redact"]
uri = "/webhooks/privacy"
```

### Webhook Handler

Capture the raw request body before JSON/body parsing, verify `X-Shopify-Hmac-Sha256`, and reject invalid HMACs before processing payloads.

```javascript
import crypto from 'crypto';

function verifyWebhookHmac(rawBody, headerValue, appSecret) {
  if (!headerValue || typeof headerValue !== 'string') return false;

  const digest = crypto
    .createHmac('sha256', appSecret)
    .update(rawBody)
    .digest('base64');

  const received = Buffer.from(headerValue, 'base64');
  const expected = Buffer.from(digest, 'base64');

  return received.length === expected.length && crypto.timingSafeEqual(received, expected);
}

app.post('/webhooks/orders/create', rawBodyMiddleware, async (req, res) => {
  const valid = verifyWebhookHmac(
    req.rawBody,
    req.headers['x-shopify-hmac-sha256'],
    process.env.SHOPIFY_API_SECRET
  );

  if (!valid) return res.status(401).send('Unauthorized');

  const order = JSON.parse(req.rawBody.toString('utf8'));
  await processOrderWebhook(order.id);
  res.status(200).send('OK');
});
```

Avoid logging full webhook payloads or customer/order data by default.

## Billing Integration

**One-time Charge:**

```graphql
mutation CreateOneTimeCharge(
  $name: String!
  $price: MoneyInput!
  $returnUrl: URL!
  $test: Boolean
) {
  appPurchaseOneTimeCreate(name: $name, price: $price, returnUrl: $returnUrl, test: $test) {
    appPurchaseOneTime { id name status confirmationUrl }
    userErrors { field message }
  }
}
```

**Subscription:**

```graphql
mutation CreateSubscription(
  $name: String!
  $returnUrl: URL!
  $lineItems: [AppSubscriptionLineItemInput!]!
  $test: Boolean
) {
  appSubscriptionCreate(name: $name, returnUrl: $returnUrl, lineItems: $lineItems, test: $test) {
    appSubscription { id name status confirmationUrl }
    userErrors { field message }
  }
}
```

**Usage Record:**

```graphql
mutation CreateUsageRecord(
  $subscriptionLineItemId: ID!
  $price: MoneyInput!
  $description: String!
) {
  appUsageRecordCreate(
    subscriptionLineItemId: $subscriptionLineItemId
    price: $price
    description: $description
  ) {
    appUsageRecord { id price { amount currencyCode } description }
    userErrors { field message }
  }
}
```

## Metafields

```graphql
mutation SetMetafields($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { id namespace key value type }
    userErrors { field message }
  }
}
```

Variables:

```json
{
  "metafields": [
    {
      "ownerId": "gid://shopify/Product/123",
      "namespace": "custom",
      "key": "instructions",
      "value": "Handle with care",
      "type": "single_line_text_field"
    }
  ]
}
```


---

Continued in [app-development-cont.md](app-development-cont.md)

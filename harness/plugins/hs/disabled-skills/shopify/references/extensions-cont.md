# Extensions Reference (continued 2/2)

## Shopify Functions

Shopify Functions are target-specific. Generate the function template, then follow the generated `schema.graphql`, `input.graphql`, and target docs for the exact output shape.

```bash
shopify app generate extension --template function
```

Representative function config:

```toml
api_version = "2026-04"

[[extensions]]
type = "function"
name = "order-discount"
handle = "order-discount"

[[extensions.targeting]]
target = "cart.lines.discounts.generate.run"
input_query = "src/run.graphql"
export = "run"
```

### Discount Function Pattern

The unified discount target `cart.lines.discounts.generate.run` handles both order and product discounts. Return `operations`, each adding candidates with a `selectionStrategy`.

```javascript
const NO_DISCOUNTS = { operations: [] };

export function run(input) {
  if (!input.cart.lines.length) return NO_DISCOUNTS;

  return {
    operations: [
      {
        orderDiscountsAdd: {
          candidates: [
            {
              targets: [{ orderSubtotal: {} }],
              value: { percentage: { value: '10.0' } },
              message: '10% off',
            },
          ],
          selectionStrategy: 'FIRST',
        },
      },
    ],
  };
}
```

- Operations: `orderDiscountsAdd` (order-level) and `productDiscountsAdd` (product-level, targets line items). `selectionStrategy`: `FIRST` or `MAXIMUM` for order/product; `ALL` for product/delivery.
- Confirm the exact `targets` shape (e.g. `orderSubtotal`, `cartLine`) against your generated `input.graphql` and the GraphQL schema explorer — do not assume legacy shapes.
- **Shipping/delivery discounts** use a separate target `cart.delivery-options.discounts.generate.run` with the `deliveryDiscountsAdd` operation (`selectionStrategy: 'ALL'`).

Payment, delivery, and validation functions return different target-specific shapes.

### Payment Customization Pattern

Target `cart.payment-methods.transform.run` (set in TOML). Operations: `paymentMethodHide`, `paymentMethodMove`, `paymentMethodRename`, `paymentTermsSet`, `orderReviewAdd`.

```javascript
const NO_PAYMENT_OPERATIONS = { operations: [] };

export function run(input) {
  const shouldHide = input.cart.lines.some((line) => line.merchandise?.product?.hasTag);
  if (!shouldHide) return NO_PAYMENT_OPERATIONS;

  return {
    operations: [
      { paymentMethodHide: { paymentMethodId: 'gid://shopify/PaymentCustomizationPaymentMethod/123' } },
    ],
  };
}
```

`placements` is optional (only `CHECKOUT` is confirmed). Confirm the payment-method ID type against your generated `input.graphql`.

### Validation Function Pattern

Target `cart.validations.generate.run` (set in TOML). Wrap errors in a `validationAdd` operation; the error field is `message` (not `localizedMessage`).

```javascript
const VALID_CART = { operations: [{ validationAdd: { errors: [] } }] };

export function run(input) {
  if (input.cart.lines.length <= 5) return VALID_CART;

  return {
    operations: [
      {
        validationAdd: {
          errors: [
            {
              message: 'Maximum 5 items allowed per order',
              target: '$.cart',
            },
          ],
        },
      },
    ],
  };
}
```

### Function APIs

Shopify Functions cover these APIs (generate the template, then follow its `schema.graphql`/`input.graphql` for the exact output shape):

- **Discounts** — `cart.lines.discounts.generate.run` (order + product)
- **Shipping/delivery discounts** — `cart.delivery-options.discounts.generate.run`
- **Validation** — `cart.validations.generate.run`
- **Payment customization** — `cart.payment-methods.transform.run`
- **Delivery customization** — hide/reorder/rename delivery options
- **Cart transform** — bundle/expand/update cart line items
- **Fulfillment constraints** — restrict how items are grouped/fulfilled
- **Order routing** — influence fulfillment-location ranking

Full target names and output shapes: https://shopify.dev/docs/apps/build/functions

## Network Requests

Extensions can call external APIs when capabilities allow it. Verify session tokens on your backend before serving merchant or customer data.

Use the global `shopify` object to get a session token (the `useApi()` hook is deprecated).

```javascript
async function fetchData() {
  const token = await shopify.sessionToken.get();
  const response = await fetch('https://your-app.com/api/data', {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response.json();
}
```

## Best Practices

**Performance:** lazy-load data, memoize expensive computations, minimize re-renders, and keep network calls narrow.

**UX:** provide clear errors, loading states, keyboard support, and target-appropriate UI.

**Security:** verify backend session tokens, sanitize user input, use HTTPS, and never expose access tokens or app secrets in extension code.

**Testing:** test on development stores, mobile/desktop, accessibility flows, and edge cases per target.

## Resources

- App Extensions: https://shopify.dev/docs/apps/build/app-extensions
- Checkout UI Extensions: https://shopify.dev/docs/api/checkout-ui-extensions
- Admin Extensions: https://shopify.dev/docs/apps/admin/extensions
- Functions: https://shopify.dev/docs/apps/build/functions
- Extension components: https://shopify.dev/docs/api/checkout-ui-extensions/components

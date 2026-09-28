# Shopify Workflow & Patterns

Development workflow, essential implementation patterns, and troubleshooting for Shopify apps, extensions, and themes. Companion detail for the core `shopify` skill.

## Development Workflow

CLI commands for app/theme dev-deploy cycles: see SKILL.md Quick Start (App Workflow, Theme Workflow).

### 1. App Development

Configure scopes in `shopify.app.toml`:

```toml
[access_scopes]
scopes = "read_products,write_products,read_orders"
```

### 2. Extension Development

Common extension types (select via the interactive picker; UI extensions use Preact + web components):
- Checkout UI
- Admin Action / Admin Block
- POS UI
- Customer Account UI
- Function

### 3. Theme Development

Beyond the Quick Start commands, use `shopify theme publish --theme=123` to promote a specific theme to live.


## Essential Patterns

### GraphQL Product Query

```graphql
query GetProducts($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    edges {
      cursor
      node {
        id
        title
        handle
        status
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
```

### Liquid Product Display

```liquid
{% for product in collection.products %}
  <div class="product-card">
    {{ product.featured_image | image_url: width: 450 | image_tag: alt: product.title }}
    <h3>{{ product.title }}</h3>
    <p>{{ product.price | money }}</p>
    <a href="{{ product.url }}">View Details</a>
  </div>
{% endfor %}
```


## Troubleshooting

**GraphQL throttling:** inspect `extensions.cost.throttleStatus` for `currentlyAvailable`, `maximumAvailable`, and `restoreRate`. Retry only after enough cost budget is restored; reduce requested fields and page sizes when possible.

**API versions:** reusable snippets should use `{api_version}` unless showing a concrete tested config. Latest stable as of 2026-06-12 is `2026-04`; review Shopify API versions quarterly. Check `X-Shopify-API-Version` in responses to detect fall-forward behavior.

**Deploy confusion:** `shopify app deploy` does not publish your hosted app code. Run your hosting provider deploy separately.

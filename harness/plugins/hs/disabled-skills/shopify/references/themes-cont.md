# Themes Reference (continued 2/2)

## Common Patterns

### Product Form with Variants

```liquid
{% form 'product', product %}
  {% unless product.has_only_default_variant %}
    {% for option in product.options_with_values %}
      <div class="product-option">
        <label>{{ option.name }}</label>
        <select name="options[{{ option.name }}]">
          {% for value in option.values %}
            <option value="{{ value }}">{{ value }}</option>
          {% endfor %}
        </select>
      </div>
    {% endfor %}
  {% endunless %}

  <input type="hidden" name="id" value="{{ product.selected_or_first_available_variant.id }}">
  <input type="number" name="quantity" value="1" min="1">
  <button type="submit" {% unless product.available %}disabled{% endunless %}>
    {% if product.available %}Add to Cart{% else %}Sold Out{% endif %}
  </button>
{% endform %}
```

### Pagination

```liquid
{% paginate collection.products by 12 %}
  {% for product in collection.products %}
    {% render 'product-card', product: product %}
  {% endfor %}

  {% if paginate.pages > 1 %}
    <nav class="pagination" aria-label="Pagination">
      {% if paginate.previous %}<a href="{{ paginate.previous.url }}">Previous</a>{% endif %}
      {% for part in paginate.parts %}
        {% if part.is_link %}<a href="{{ part.url }}">{{ part.title }}</a>{% else %}<span aria-current="page">{{ part.title }}</span>{% endif %}
      {% endfor %}
      {% if paginate.next %}<a href="{{ paginate.next.url }}">Next</a>{% endif %}
    </nav>
  {% endif %}
{% endpaginate %}
```

### Cart AJAX

Use `window.Shopify.routes.root` so requests stay locale-aware on Shopify Markets storefronts (e.g. `/en-ca/cart/add.js`).

```javascript
fetch(window.Shopify.routes.root + 'cart/add.js', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ id: variantId, quantity: 1 })
}).then(res => res.json());

fetch(window.Shopify.routes.root + 'cart/change.js', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ id: lineItemKey, quantity: 2 })
}).then(res => res.json());
```

## Metafields in Themes

```liquid
{{ product.metafields.custom.care_instructions }}
{{ product.metafields.custom.material.value }}

{% if product.metafields.custom.featured %}
  <span class="badge">Featured</span>
{% endif %}
```

## Best Practices

**Performance:** size images with `image_url`, lazy-load non-hero images, minimize Liquid logic, defer non-critical JavaScript.

**Accessibility:** use semantic HTML, preserve alt text, support keyboard navigation, and maintain contrast.

**SEO:** use descriptive titles, meta descriptions, headings, and structured data where appropriate.

**Code Quality:** follow Shopify theme guidelines, keep sections focused, and run Theme Check before publishing.

## Resources

- Theme Development: https://shopify.dev/docs/themes
- Liquid Reference: https://shopify.dev/docs/api/liquid
- Theme Blocks: https://shopify.dev/docs/storefronts/themes/architecture/blocks
- Dawn Theme: https://github.com/Shopify/dawn
- Theme Check: https://shopify.dev/docs/themes/tools/theme-check

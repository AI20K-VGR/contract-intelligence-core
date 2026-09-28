# Themes Reference

Guide for developing Shopify themes with Liquid templating.

## Liquid Templating

### Syntax Basics

**Objects (Output):**
```liquid
{{ product.title }}
{{ product.price | money }}
{{ customer.email }}
```

**Tags (Logic):**
```liquid
{% if product.available %}
  <button>Add to Cart</button>
{% else %}
  <p>Sold Out</p>
{% endif %}

{% for product in collection.products %}
  {{ product.title }}
{% endfor %}
```

**Filters (Transform):**
```liquid
{{ product.title | upcase }}
{{ product.price | money }}
{{ product.description | strip_html | truncate: 100 }}
{{ product.featured_image | image_url: width: 450 }}
{{ product.featured_image | image_url: width: 450 | image_tag: alt: product.title }}
{{ 'now' | date: '%B %d, %Y' }}
```

Use `image_url` for a URL, `image_tag` when rendering an `<img>` tag. Older `img_url` snippets are deprecated and should not be copied into new theme code.

### Common Objects

**Product:**
```liquid
{{ product.id }}
{{ product.title }}
{{ product.handle }}
{{ product.description }}
{{ product.price }}
{{ product.compare_at_price }}
{{ product.available }}
{{ product.type }}
{{ product.vendor }}
{{ product.tags }}
{{ product.images }}
{{ product.variants }}
{{ product.featured_image }}
{{ product.url }}
```

**Collection:**
```liquid
{{ collection.title }}
{{ collection.handle }}
{{ collection.description }}
{{ collection.products }}
{{ collection.products_count }}
{{ collection.image }}
{{ collection.url }}
```

**Cart:**
```liquid
{{ cart.item_count }}
{{ cart.total_price }}
{{ cart.items }}
{{ cart.note }}
{{ cart.attributes }}
```

### Common Filters

**String:** `upcase`, `downcase`, `capitalize`, `strip_html`, `truncate`, `replace`

**Number:** `money`, `round`, `ceil`, `floor`, `times`, `divided_by`, `plus`, `minus`

**Array:** `join`, `first`, `last`, `size`, `map`, `where`

**Image:**
```liquid
{{ image | image_url: width: 800 }}
{{ image | image_url: width: 800 | image_tag: alt: image.alt, loading: 'lazy' }}
```

## Theme Architecture

### Directory Structure

```text
theme/
├── assets/              # CSS, JS, images
├── config/              # Theme settings
├── layout/              # Base templates
├── locales/             # Translations
├── sections/            # Reusable blocks
├── snippets/            # Small components
└── templates/           # Page templates
```

### Layout

Base template wrapping all pages (`layout/theme.liquid`):

```liquid
<!DOCTYPE html>
<html lang="{{ request.locale.iso_code }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ page_title }}</title>
  {{ content_for_header }}
  <link rel="stylesheet" href="{{ 'theme.css' | asset_url }}">
</head>
<body>
  {% section 'header' %}
  <main>{{ content_for_layout }}</main>
  {% section 'footer' %}
  <script src="{{ 'theme.js' | asset_url }}" defer></script>
</body>
</html>
```

### JSON Templates

Page-specific structures (`templates/product.json`):

```json
{
  "sections": {
    "main": {
      "type": "product-template",
      "settings": {
        "show_vendor": true,
        "show_quantity_selector": true
      }
    },
    "recommendations": {
      "type": "product-recommendations"
    }
  },
  "order": ["main", "recommendations"]
}
```

### Product Template Example

```liquid
<div class="product">
  <div class="product-images">
    {{ product.featured_image | image_url: width: 900 | image_tag: alt: product.title, loading: 'eager' }}
  </div>

  <div class="product-details">
    <h1>{{ product.title }}</h1>
    <p class="price">{{ product.price | money }}</p>

    {% form 'product', product %}
      <select name="id">
        {% for variant in product.variants %}
          <option value="{{ variant.id }}">{{ variant.title }} - {{ variant.price | money }}</option>
        {% endfor %}
      </select>
      <button type="submit">Add to Cart</button>
    {% endform %}
  </div>
</div>
```

### Sections

Reusable content blocks (`sections/product-grid.liquid`):

```liquid
<div class="product-grid">
  {% for product in section.settings.collection.products %}
    <div class="product-card">
      <a href="{{ product.url }}">
        {{ product.featured_image | image_url: width: 450 | image_tag: alt: product.title, loading: 'lazy' }}
        <h3>{{ product.title }}</h3>
        <p>{{ product.price | money }}</p>
      </a>
    </div>
  {% endfor %}
</div>
```

### Snippets

Small reusable components (`snippets/product-card.liquid`):

```liquid
<div class="product-card">
  <a href="{{ product.url }}">
    {% if product.featured_image %}
      {{ product.featured_image | image_url: width: 450 | image_tag: alt: product.title, loading: 'lazy' }}
    {% endif %}
    <h3>{{ product.title }}</h3>
    <p class="price">{{ product.price | money }}</p>
    {% if product.compare_at_price > product.price %}
      <p class="sale-price">{{ product.compare_at_price | money }}</p>
    {% endif %}
  </a>
</div>
```

Include snippet:
```liquid
{% render 'product-card', product: product %}
```

### Theme Blocks

Theme Blocks are the current standard for building flexible sections: a section renders its blocks with `{% content_for 'blocks' %}`, and merchants add, remove, and reorder theme blocks (`@theme`) and app blocks (`@app`) in the theme editor.

```liquid
<div class="custom-section">
  {% content_for 'blocks' %}
</div>

{% schema %}
{
  "name": "Custom section",
  "blocks": [
    { "type": "@theme" },
    { "type": "@app" }
  ],
  "presets": [{ "name": "Custom section" }]
}
{% endschema %}
```

See the Theme Blocks docs for nested blocks, block-level settings, and static blocks: https://shopify.dev/docs/storefronts/themes/architecture/blocks

## Development Workflow

```bash
shopify theme init
shopify theme dev
shopify theme pull --live
shopify theme push --development
shopify theme push --unpublished
shopify theme check
shopify theme check --auto-correct
```


---

Continued in [themes-cont.md](themes-cont.md)

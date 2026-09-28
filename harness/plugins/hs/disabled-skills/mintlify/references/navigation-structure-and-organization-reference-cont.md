# Navigation Structure and Organization Reference (continued 2/3)

## Products

Partition docs into products with independent navigation.

```json
{
  "products": [
    {
      "name": "Product A",
      "slug": "product-a",
      "icon": "rocket"
    },
    {
      "name": "Product B",
      "slug": "product-b",
      "icon": "star"
    },
    {
      "name": "Product C",
      "slug": "product-c",
      "icon": "zap"
    }
  ],
  "navigation": [
    {
      "group": "Getting Started",
      "pages": ["product-a/intro", "product-a/quickstart"],
      "product": "product-a"
    },
    {
      "group": "Getting Started",
      "pages": ["product-b/intro", "product-b/setup"],
      "product": "product-b"
    },
    {
      "group": "Overview",
      "pages": ["product-c/intro"],
      "product": "product-c"
    }
  ]
}
```

Users pick product via top switcher; each has its own navigation tree.

## Versions

Manage multiple documentation versions.

```json
{
  "versions": [
    {
      "name": "v3.0",
      "slug": "v3"
    },
    {
      "name": "v2.0",
      "slug": "v2"
    },
    {
      "name": "v1.0 (Legacy)",
      "slug": "v1"
    }
  ],
  "navigation": [
    {
      "group": "Getting Started",
      "pages": ["v3/introduction", "v3/installation"],
      "version": "v3"
    },
    {
      "group": "Getting Started",
      "pages": ["v2/introduction", "v2/installation"],
      "version": "v2"
    },
    {
      "group": "Getting Started",
      "pages": ["v1/introduction", "v1/installation"],
      "version": "v1"
    }
  ]
}
```

Users switch versions via dropdown; each keeps independent navigation.

## Languages

Multi-language documentation with i18n support.

```json
{
  "languages": [
    {
      "name": "English",
      "slug": "en"
    },
    {
      "name": "Español",
      "slug": "es"
    },
    {
      "name": "Français",
      "slug": "fr"
    },
    {
      "name": "Deutsch",
      "slug": "de"
    },
    {
      "name": "日本語",
      "slug": "ja"
    },
    {
      "name": "中文",
      "slug": "zh"
    }
  ],
  "navigation": [
    {
      "group": "Getting Started",
      "pages": ["en/introduction", "en/quickstart"],
      "language": "en"
    },
    {
      "group": "Primeros Pasos",
      "pages": ["es/introduccion", "es/inicio-rapido"],
      "language": "es"
    },
    {
      "group": "Commencer",
      "pages": ["fr/introduction", "fr/demarrage"],
      "language": "fr"
    }
  ]
}
```

### Supported Locales

28+ languages supported:

- `en` - English
- `es` - Español
- `fr` - Français
- `de` - Deutsch
- `it` - Italiano
- `pt` - Português
- `pt-BR` - Português (Brasil)
- `zh` - 中文
- `zh-TW` - 中文 (台灣)
- `ja` - 日本語
- `ko` - 한국어
- `ru` - Русский
- `ar` - العربية
- `hi` - हिन्दी
- `nl` - Nederlands
- `pl` - Polski
- `tr` - Türkçe
- `sv` - Svenska
- `da` - Dansk
- `no` - Norsk
- `fi` - Suomi
- `cs` - Čeština
- `hu` - Magyar
- `ro` - Română
- `th` - ไทย
- `vi` - Tiếng Việt
- `id` - Bahasa Indonesia
- `ms` - Bahasa Melayu

## Combining Products, Versions, and Languages

Complex navigation with all organizational patterns:

```json
{
  "products": [
    {
      "name": "Platform API",
      "slug": "api"
    },
    {
      "name": "SDK",
      "slug": "sdk"
    }
  ],
  "versions": [
    {
      "name": "v2.0",
      "slug": "v2"
    },
    {
      "name": "v1.0",
      "slug": "v1"
    }
  ],
  "languages": [
    {
      "name": "English",
      "slug": "en"
    },
    {
      "name": "Español",
      "slug": "es"
    }
  ],
  "navigation": [
    {
      "group": "Getting Started",
      "pages": ["api/v2/en/intro"],
      "product": "api",
      "version": "v2",
      "language": "en"
    },
    {
      "group": "Primeros Pasos",
      "pages": ["api/v2/es/intro"],
      "product": "api",
      "version": "v2",
      "language": "es"
    },
    {
      "group": "Getting Started",
      "pages": ["sdk/v2/en/intro"],
      "product": "sdk",
      "version": "v2",
      "language": "en"
    }
  ]
}
```


---

Continued in [navigation-structure-and-organization-reference-cont2.md](navigation-structure-and-organization-reference-cont2.md)

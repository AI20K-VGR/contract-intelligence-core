# Deployment and Continuous Integration Reference (continued 3/3)

## Authentication

Protect docs with authentication.

### Mintlify Auth (Built-in)

1. **Enable in Dashboard:**
   - Go to Settings > Authentication
   - Enable "Require Authentication"
   - Choose auth method

2. **Auth Methods:**
   - Email allowlist
   - Google OAuth
   - GitHub OAuth
   - Custom SSO (SAML)

3. **Configure:**
   ```json
   {
     "auth": {
       "enabled": true,
       "method": "google",
       "allowedDomains": ["company.com"]
     }
   }
   ```

### Custom Authentication

Integrate with existing auth system:

1. **Reverse Proxy:**
   - Place auth layer before Mintlify
   - Validate session/token
   - Proxy authenticated requests

2. **Example (Nginx + OAuth2 Proxy):**
   ```nginx
   location /docs {
       auth_request /oauth2/auth;
       error_page 401 = /oauth2/sign_in;

       proxy_pass https://your-site.mintlify.app;
   }
   ```

## Content Security Policy (CSP)

Configure CSP headers for security.

### Required CSP Directives

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'unsafe-inline' 'unsafe-eval' https://mintlify.com;
  style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
  font-src 'self' https://fonts.gstatic.com;
  img-src 'self' data: https:;
  connect-src 'self' https://api.mintlify.com;
  frame-src 'self' https://mintlify.com;
```

### Cloudflare Configuration

```javascript
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const response = await fetch(request)
  const newHeaders = new Headers(response.headers)

  newHeaders.set(
    'Content-Security-Policy',
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://mintlify.com"
  )

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders
  })
}
```

## Environment-Specific Configuration

Manage configurations per environment.

### Multiple Config Files

```
docs/
├── docs.json              # Production config
├── docs.staging.json      # Staging config
├── docs.development.json  # Development config
```

### Build with Environment Config

```bash
# Development
MINTLIFY_CONFIG=docs.development.json mint dev

# Staging
MINTLIFY_CONFIG=docs.staging.json mint build

# Production
mint build  # Uses docs.json by default
```

### Environment Variables

Inject environment-specific values:

```json
{
  "name": "${DOCS_SITE_NAME}",
  "api": {
    "playground": {
      "proxy": "${API_BASE_URL}"
    }
  },
  "integrations": {
    "ga4": {
      "measurementId": "${GA4_MEASUREMENT_ID}"
    }
  }
}
```

**GitHub Actions:**

```yaml
- name: Build docs
  run: mint build
  env:
    DOCS_SITE_NAME: "My Docs"
    API_BASE_URL: "https://api.example.com"
    GA4_MEASUREMENT_ID: "G-XXXXXXXXXX"
```

## Cache Configuration

Optimize caching performance.

### CDN Cache Headers

```
Cache-Control: public, max-age=3600, s-maxage=86400
```

### Cloudflare Page Rules

```
URL: docs.example.com/*
Settings:
  - Cache Level: Standard
  - Edge Cache TTL: 1 day
  - Browser Cache TTL: 1 hour
```

### Invalidation

Invalidate cache after deployment:

**Cloudflare:**
```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/purge_cache" \
  -H "Authorization: Bearer ${CF_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{"purge_everything":true}'
```

**AWS CloudFront:**
```bash
aws cloudfront create-invalidation \
  --distribution-id ${DISTRIBUTION_ID} \
  --paths "/*"
```

## Deployment Checklist

Pre-deployment validation:

- [ ] Run `mint validate` - Check configuration
- [ ] Run `mint broken-links` - Verify all links work
- [ ] Run `mint a11y` - Check accessibility
- [ ] Run `mint openapi-check` - Validate API specs
- [ ] Test preview deployment
- [ ] Verify custom domain DNS
- [ ] Check SSL certificate
- [ ] Test authentication (if enabled)
- [ ] Validate CSP headers
- [ ] Review analytics integration
- [ ] Check mobile responsiveness
- [ ] Test search functionality
- [ ] Verify social preview images

# Deployment and Continuous Integration Reference

Guide for deploying Mintlify documentation with hosting platforms and CI/CD pipelines.

## Auto-Deploy from Git

Mintlify auto-deploys from connected Git repositories.

### GitHub Integration

1. **Connect Repository:**
   - Go to Mintlify dashboard
   - Click "Connect Repository"
   - Authorize GitHub access
   - Select repository

2. **Configure Branch:**
   - Set main branch (e.g., `main`, `master`)
   - Optionally enable preview deployments for PRs

3. **Auto-Deploy:**
   - Push to main branch triggers production deployment
   - Pull requests trigger preview deployments
   - Deployment status shows in GitHub checks

### GitLab Integration

1. **Connect Repository:**
   - Go to Mintlify dashboard
   - Select GitLab integration
   - Authorize GitLab access
   - Choose repository and branch

2. **Deploy on Push:**
   - Commits to configured branch auto-deploy
   - Merge requests can trigger previews

### GitHub Enterprise Server

For self-hosted GitHub instances:

1. **Configuration:**
   - Provide GitHub Enterprise Server URL
   - Generate personal access token with repo permissions
   - Add webhook URL to repository

2. **Webhook Setup:**
   ```
   Payload URL: https://api.mintlify.com/webhook/github-enterprise
   Content type: application/json
   Events: Push, Pull request
   ```

## Preview Deployments

Preview documentation changes before merging.

### Pull Request Previews

Automatically generate preview deployments for PRs:

1. **Enable in Dashboard:**
   - Navigate to Settings > Deployments
   - Enable "Preview Deployments"
   - Choose PR branches to deploy

2. **Access Previews:**
   - Preview URL appears in PR checks
   - Format: `https://preview-{pr-number}.mintlify.app`
   - Auto-updates on new commits

3. **Cleanup:**
   - Previews auto-delete after PR merge/close
   - Configurable retention period

### Branch Previews

Deploy specific branches for testing:

1. **Configure Branch Patterns:**
   ```json
   {
     "deployments": {
       "preview": {
         "branches": ["staging", "dev", "feature/*"]
       }
     }
   }
   ```

2. **Access:**
   - URL format: `https://{branch-name}.mintlify.app`
   - Auto-deploy on branch push

## Custom Domain

Connect custom domain to documentation.

### DNS Configuration

1. **Add DNS Records:**

   **Apex domain (example.com):**
   ```
   Type: TXT
   Name: @
   Value: mintlify-domain-verification={verification-code}

   Type: CNAME (or ALIAS/ANAME)
   Name: @
   Value: mintlify-dns.com
   ```

   **Subdomain (docs.example.com):**
   ```
   Type: TXT
   Name: docs
   Value: mintlify-domain-verification={verification-code}

   Type: CNAME
   Name: docs
   Value: mintlify-dns.com
   ```

2. **Verify in Dashboard:**
   - Go to Settings > Custom Domain
   - Enter domain name
   - Click "Verify DNS"
   - Wait for SSL certificate provisioning (5-15 minutes)

### Multiple Domains

Point multiple domains to same documentation:

```
docs.example.com → Primary domain
documentation.example.com → Redirect to primary
help.example.com → Redirect to primary
```

Configure redirects in dashboard or via DNS.

## Subpath Hosting

Host documentation on subpath (e.g., `example.com/docs`).

### Reverse Proxy Configuration

**Nginx:**

```nginx
location /docs {
    proxy_pass https://your-site.mintlify.app;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Rewrite path
    rewrite ^/docs(/.*)?$ $1 break;
}
```

**Apache:**

```apache
<Location /docs>
    ProxyPass https://your-site.mintlify.app
    ProxyPassReverse https://your-site.mintlify.app
    ProxyPreserveHost On

    # Rewrite
    RewriteEngine On
    RewriteRule ^/docs(/.*)?$ $1 [PT]
</Location>
```

**Cloudflare Workers:**

```javascript
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)

  if (url.pathname.startsWith('/docs')) {
    const newUrl = url.pathname.replace(/^\/docs/, '')
    return fetch(`https://your-site.mintlify.app${newUrl}`, {
      headers: request.headers
    })
  }

  return fetch(request)
}
```

### Base Path Configuration

Configure base path in `docs.json`:

```json
{
  "basePath": "/docs"
}
```

All routes prefixed with `/docs`:
- `/docs/introduction`
- `/docs/api/users`
- `/docs/guides/quickstart`


---

Continued in [deployment-and-continuous-integration-reference-cont.md](deployment-and-continuous-integration-reference-cont.md)

# Deployment and Continuous Integration Reference (continued 2/3)

## Platform-Specific Deployment

### Vercel

Deploy Mintlify docs alongside Next.js app.

1. **Install Mintlify:**
   ```bash
   npm install -D mintlify
   ```

2. **Add Build Script:**
   ```json
   {
     "scripts": {
       "docs:build": "mintlify build",
       "docs:dev": "mintlify dev"
     }
   }
   ```

3. **Configure Vercel:**
   ```json
   {
     "buildCommand": "npm run docs:build",
     "outputDirectory": ".mintlify/out",
     "routes": [
       {
         "src": "/docs/(.*)",
         "dest": "/.mintlify/out/$1"
       }
     ]
   }
   ```

4. **Deploy:**
   ```bash
   vercel
   ```

### Cloudflare Pages

1. **Build Settings:**
   - Build command: `mintlify build`
   - Build output directory: `.mintlify/out`
   - Root directory: `/` (or docs subfolder)

2. **Environment Variables:**
   - Set `NODE_VERSION=18` or higher

3. **Deploy:**
   - Connect GitHub repository
   - Configure branch: `main`
   - Cloudflare auto-builds on push

### AWS (Route 53 + CloudFront)

Host static Mintlify build on AWS.

1. **Build Docs:**
   ```bash
   mintlify build
   ```

2. **Upload to S3:**
   ```bash
   aws s3 sync .mintlify/out s3://docs-bucket/ \
     --delete \
     --cache-control "public, max-age=3600"
   ```

3. **CloudFront Distribution:**
   - Origin: S3 bucket
   - Default root object: `index.html`
   - Error pages: Route 404 to `/404.html`

4. **Route 53:**
   - Create A record (alias to CloudFront distribution)
   - Enable IPv6 (AAAA record)

5. **SSL Certificate:**
   - Request certificate in AWS Certificate Manager
   - Validate domain ownership
   - Attach to CloudFront distribution

## Monorepo Setup

Deploy documentation from monorepo structure.

### Directory Structure

```
monorepo/
├── packages/
│   ├── app/
│   ├── api/
│   └── docs/           # Mintlify documentation
│       ├── docs.json
│       ├── introduction.mdx
│       └── api/
└── package.json
```

### Configuration

**Root `package.json`:**

```json
{
  "workspaces": ["packages/*"],
  "scripts": {
    "docs:dev": "npm run dev --workspace=packages/docs",
    "docs:build": "npm run build --workspace=packages/docs"
  }
}
```

**`packages/docs/package.json`:**

```json
{
  "name": "docs",
  "version": "1.0.0",
  "scripts": {
    "dev": "mintlify dev",
    "build": "mintlify build"
  },
  "devDependencies": {
    "mintlify": "latest"
  }
}
```

### CI/CD for Monorepo

**GitHub Actions:**

```yaml
name: Deploy Docs

on:
  push:
    branches: [main]
    paths:
      - 'packages/docs/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: 18

      - name: Install dependencies
        run: npm ci

      - name: Build docs
        run: npm run docs:build

      - name: Deploy
        run: npx mintlify deploy
        env:
          MINTLIFY_TOKEN: ${{ secrets.MINTLIFY_TOKEN }}
```

## CI/CD Validation

Validate documentation in CI pipeline.

### GitHub Actions

```yaml
name: Validate Docs

on:
  pull_request:
    paths:
      - 'docs/**'
      - 'docs.json'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: 18

      - name: Install Mintlify
        run: npm install -g mintlify

      - name: Validate config
        run: mint validate

      - name: Check broken links
        run: mint broken-links

      - name: Check accessibility
        run: mint a11y

      - name: Validate OpenAPI
        run: mint openapi-check
```

### GitLab CI

```yaml
validate-docs:
  image: node:18
  stage: test
  only:
    changes:
      - docs/**
      - docs.json
  script:
    - npm install -g mintlify
    - mint validate
    - mint broken-links
    - mint openapi-check
```

### CircleCI

```yaml
version: 2.1

jobs:
  validate:
    docker:
      - image: cimg/node:18.0
    steps:
      - checkout
      - run:
          name: Install Mintlify
          command: npm install -g mintlify
      - run:
          name: Validate
          command: |
            mint validate
            mint broken-links
            mint a11y

workflows:
  docs:
    jobs:
      - validate:
          filters:
            branches:
              only:
                - main
                - develop
```


---

Continued in [deployment-and-continuous-integration-reference-cont2.md](deployment-and-continuous-integration-reference-cont2.md)

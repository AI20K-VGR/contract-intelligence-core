# Backend DevOps Practices (continued 2/2)

## CI/CD Pipelines

### GitHub Actions (Modern, Integrated)

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run linter
        run: npm run lint

      - name: Run tests
        run: npm run test:ci

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Snyk scan
        uses: snyk/actions/node@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}

      - name: Container scan
        run: |
          docker build -t myapp:${{ github.sha }} .
          docker scan myapp:${{ github.sha }}

  deploy:
    needs: [test, security]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3

      - name: Build and push Docker image
        run: |
          echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io -u ${{ github.actor }} --password-stdin
          docker build -t ghcr.io/${{ github.repository }}:${{ github.sha }} .
          docker push ghcr.io/${{ github.repository }}:${{ github.sha }}

      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/api api=ghcr.io/${{ github.repository }}:${{ github.sha }}
          kubectl rollout status deployment/api
```

## Monitoring & Observability

### Three Pillars of Observability

**1. Metrics (Prometheus + Grafana)**

```typescript
import { Counter, Histogram, register } from 'prom-client';

// Request counter
const httpRequestTotal = new Counter({
  name: 'http_requests_total',
  help: 'Total HTTP requests',
  labelNames: ['method', 'route', 'status'],
});

// Response time histogram
const httpRequestDuration = new Histogram({
  name: 'http_request_duration_seconds',
  help: 'HTTP request duration',
  labelNames: ['method', 'route'],
  buckets: [0.1, 0.5, 1, 2, 5],
});

// Middleware to track metrics
app.use((req, res, next) => {
  const start = Date.now();

  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    httpRequestTotal.inc({ method: req.method, route: req.route?.path, status: res.statusCode });
    httpRequestDuration.observe({ method: req.method, route: req.route?.path }, duration);
  });

  next();
});

// Metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});
```

**2. Logs (ELK Stack - Elasticsearch, Logstash, Kibana)**

```typescript
import winston from 'winston';
import { ElasticsearchTransport } from 'winston-elasticsearch';

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [
    new winston.transports.Console(),
    new ElasticsearchTransport({
      level: 'info',
      clientOpts: { node: 'http://localhost:9200' },
      index: 'logs',
    }),
  ],
});

// Structured logging
logger.info('User created', {
  userId: user.id,
  email: user.email,
  ipAddress: req.ip,
  userAgent: req.headers['user-agent'],
});
```

**3. Traces (Jaeger/OpenTelemetry)**

```typescript
import { NodeSDK } from '@opentelemetry/sdk-node';
import { JaegerExporter } from '@opentelemetry/exporter-jaeger';

const sdk = new NodeSDK({
  traceExporter: new JaegerExporter({
    endpoint: 'http://localhost:14268/api/traces',
  }),
  serviceName: 'api-service',
});

sdk.start();

// Traces automatically captured for HTTP requests, database queries, etc.
```

### Health Checks

```typescript
// Liveness probe - Is the app running?
app.get('/health/liveness', (req, res) => {
  res.status(200).json({ status: 'ok', timestamp: Date.now() });
});

// Readiness probe - Is the app ready to serve traffic?
app.get('/health/readiness', async (req, res) => {
  const checks = {
    database: await checkDatabase(),
    redis: await checkRedis(),
    externalAPI: await checkExternalAPI(),
  };

  const isReady = Object.values(checks).every(Boolean);
  res.status(isReady ? 200 : 503).json({
    status: isReady ? 'ready' : 'not ready',
    checks,
  });
});

async function checkDatabase() {
  try {
    await db.query('SELECT 1');
    return true;
  } catch {
    return false;
  }
}
```

## Secrets Management

### HashiCorp Vault

```bash
# Store secret
vault kv put secret/myapp/db password=super-secret

# Retrieve secret
vault kv get -field=password secret/myapp/db
```

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
type: Opaque
stringData:
  url: postgresql://user:pass@host:5432/db
---
# Reference in deployment
env:
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: db-secret
      key: url
```

## Infrastructure as Code (Terraform)

```hcl
# main.tf
resource "aws_db_instance" "main" {
  identifier        = "myapp-db"
  engine            = "postgres"
  engine_version    = "15.3"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  username          = "admin"
  password          = var.db_password

  backup_retention_period = 7
  skip_final_snapshot     = false
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "myapp-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
}
```

## DevOps Checklist

- [ ] CI/CD pipeline configured (GitHub Actions/GitLab CI/Jenkins)
- [ ] Docker multi-stage builds implemented
- [ ] Kubernetes deployment manifests created
- [ ] Blue-green or canary deployment strategy
- [ ] Feature flags configured (LaunchDarkly/Unleash)
- [ ] Health checks (liveness + readiness probes)
- [ ] Monitoring: Prometheus + Grafana
- [ ] Logging: ELK Stack or similar
- [ ] Distributed tracing: Jaeger/OpenTelemetry
- [ ] Secrets management (Vault/AWS Secrets Manager)
- [ ] Infrastructure as Code (Terraform/CloudFormation)
- [ ] Autoscaling configured
- [ ] Backup and disaster recovery plan

## Resources

- **Kubernetes:** https://kubernetes.io/docs/
- **Docker:** https://docs.docker.com/
- **Prometheus:** https://prometheus.io/docs/
- **OpenTelemetry:** https://opentelemetry.io/docs/
- **Terraform:** https://www.terraform.io/docs/

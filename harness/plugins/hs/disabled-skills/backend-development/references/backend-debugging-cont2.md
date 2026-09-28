# Backend Debugging Strategies (continued 3/4)

## Production Debugging

### Application Performance Monitoring (APM)

**New Relic**
```typescript
// newrelic.js
export const config = {
  app_name: ['My Backend API'],
  license_key: process.env.NEW_RELIC_LICENSE_KEY,
  logging: { level: 'info' },
  distributed_tracing: { enabled: true },
};

// Import at app entry
import 'newrelic';
```

**DataDog**
```typescript
import tracer from 'dd-trace';

tracer.init({
  service: 'backend-api',
  env: process.env.NODE_ENV,
  version: '1.0.0',
  logInjection: true
});
```

**Sentry (Error Tracking)**
```typescript
import * as Sentry from '@sentry/node';

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 1.0,
});

// Capture errors
try {
  await riskyOperation();
} catch (error) {
  Sentry.captureException(error, {
    user: { id: userId },
    tags: { operation: 'payment' },
  });
}
```

### Distributed Tracing

**OpenTelemetry (Vendor-Agnostic)**
```typescript
import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { JaegerExporter } from '@opentelemetry/exporter-jaeger';

const sdk = new NodeSDK({
  traceExporter: new JaegerExporter({
    endpoint: 'http://localhost:14268/api/traces',
  }),
  instrumentations: [getNodeAutoInstrumentations()],
});

sdk.start();

// Traces HTTP, database, Redis automatically
```

### Log Aggregation

**ELK Stack (Elasticsearch, Logstash, Kibana)**
```yaml
# docker-compose.yml
version: '3'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
    ports:
      - 9200:9200

  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - 5601:5601
```

**Loki + Grafana (Lightweight)**
```yaml
# promtail config for log shipping
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: system
    static_configs:
      - targets:
          - localhost
        labels:
          job: backend-api
          __path__: /var/log/app/*.log
```


---

Continued in [backend-debugging-cont3.md](backend-debugging-cont3.md)

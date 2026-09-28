---
name: hs:devops
injectable: true
description: Deploy to Cloudflare (Workers, R2, D1), Docker, GCP (Cloud Run, GKE), Kubernetes (kubectl, Helm). Use for serverless, containers, CI/CD, GitOps, security audit.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch]
argument-hint: "[platform] [task]"
metadata:
  compliance-tier: workflow
---

# DevOps Skill

Deploy/manage cloud infra: Cloudflare, Docker, GCP, Kubernetes.

**Probe-first ★** (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/agent-operational-discipline.md` — the priority discipline): how the infra actually responds — a `kubectl` / `gcloud` / `wrangler` result,
a container's real startup — is established by RUNNING the command, not by reading the provider's docs. A docs / flag claim is a *hypothesis*, NOT a probe; an unrun claim is `[ASSUMED]`, never OBSERVED, and
no "deployed" / "healthy" from reasoning alone.

## When to Use

- Deploy serverless apps to Cloudflare Workers/Pages
- Containerize apps with Docker, Docker Compose
- Manage GCP with gcloud CLI (Cloud Run, GKE, Cloud SQL)
- Kubernetes cluster management (kubectl, Helm)
- GitOps workflows (Argo CD, Flux)
- CI/CD pipelines, multi-region deployments
- Security audits, RBAC, network policies

## Platform Selection

| Need | Choose |
|------|--------|
| Sub-50ms latency globally | Cloudflare Workers |
| Large file storage (zero egress) | Cloudflare R2 |
| SQL database (global reads) | Cloudflare D1 |
| Containerized workloads | Docker + Cloud Run/GKE |
| Enterprise Kubernetes | GKE |
| Managed relational DB | Cloud SQL |
| Static site + API | Cloudflare Pages |
| Container orchestration | Kubernetes |
| Package management for K8s | Helm |

## Quick Start

```bash
# Cloudflare Worker
wrangler init my-worker && cd my-worker && wrangler deploy

# Docker
docker build -t myapp . && docker run -p 3000:3000 myapp

# GCP Cloud Run
gcloud run deploy my-service --image gcr.io/project/image --region us-central1

# Kubernetes
kubectl apply -f manifests/ && kubectl get pods
```

## Reference Navigation

### Cloudflare Platform
- `cloudflare-platform.md` - Edge computing overview
- `cloudflare-workers-basics.md` / `cloudflare-workers-basics-cont.md` - Handler types, patterns
- `cloudflare-workers-advanced.md` / `cloudflare-workers-advanced-cont.md` - Performance, optimization
- `cloudflare-workers-apis.md` / `cloudflare-workers-apis-cont.md` - Runtime APIs, bindings
- `cloudflare-r2-storage.md` - Object storage, S3 compatibility
- `cloudflare-d1-kv.md` - D1 SQLite, KV store
- `browser-rendering.md` / `browser-rendering-cont.md` - Puppeteer automation

### Docker
- `docker-basics.md` - Dockerfile, images, containers
- `docker-compose.md` - Multi-container apps

### Google Cloud
- `gcloud-platform.md` - gcloud CLI, authentication
- `gcloud-services.md` / `gcloud-services-cont.md` - Compute Engine, GKE, Cloud Run

### Kubernetes
- `kubernetes-basics.md` - Core concepts, architecture, workloads
- `kubernetes-kubectl.md` - Essential commands, debugging workflow
- `kubernetes-helm.md` / `kubernetes-helm-advanced.md` - Helm charts, templates
- `kubernetes-security.md` / `kubernetes-security-advanced.md` - RBAC, secrets
- `kubernetes-workflows.md` / `kubernetes-workflows-advanced.md` - GitOps, CI/CD
- `kubernetes-troubleshooting.md` / `kubernetes-troubleshooting-advanced.md` - Debug

### Scripts
- `scripts/cloudflare_deploy.py` - Automate Worker deployments
- `scripts/docker_optimize.py` - Analyze Dockerfiles

## Common Pitfalls to Check (unenforced — no gate backs these)

**Security:** Non-root containers, RBAC, secrets in env vars, image scanning
**Performance:** Multi-stage builds, edge caching, resource limits
**Cost:** R2 for large egress, caching, right-size resources
**Development:** Docker Compose local dev, wrangler dev, version control IaC

## Resources

- Cloudflare: https://developers.cloudflare.com
- Docker: https://docs.docker.com
- GCP: https://cloud.google.com/docs
- Kubernetes: https://kubernetes.io/docs
- Helm: https://helm.sh/docs

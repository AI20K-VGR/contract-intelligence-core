# Color palette

**Single source of truth for all colors.** Edit this file to customize.

---

## Default palette (platform-agnostic)

| Component type | Background | Stroke | Example |
|---|---|---|---|
| Frontend/UI | `#a5d8ff` | `#1971c2` | React, Next.js, web app |
| Backend/API | `#d0bfff` | `#7048e8` | API server, processor |
| Database | `#b2f2bb` | `#2f9e44` | PostgreSQL, MySQL, MongoDB |
| Storage | `#ffec99` | `#f08c00` | Object storage, filesystem |
| AI/ML Services | `#e599f7` | `#9c36b5` | ML model, AI API |
| External APIs | `#ffc9c9` | `#e03131` | Third-party service |
| Queue/Event | `#fff3bf` | `#fab005` | Kafka, RabbitMQ, SQS |
| Cache | `#ffe8cc` | `#fd7e14` | Redis, Memcached |
| Decision/Gate | `#ffd8a8` | `#e8590c` | Conditional, router |
| Zone/Group | `#e9ecef` | `#868e96` | Logical grouping |
| Monitoring | `#d3f9d8` | `#40c057` | Prometheus, Grafana |
| Users/Actors | `#e7f5ff` | `#1971c2` | User ellipse |
| Network/Security | `#dee2e6` | `#495057` | VPC, IAM, firewall |
| Classification | `#99e9f2` | `#0c8599` | Router, classifier |

**Rule**: Always pair a darker stroke with a lighter fill.
**Rule**: Same role = same color. Max 3-4 fill colors per diagram.

---

## Semantic shape colors (diagram design philosophy)

| Purpose | Fill | Stroke |
|---|---|---|
| Primary/Neutral | `#3b82f6` | `#1e3a5f` |
| Secondary | `#60a5fa` | `#1e3a5f` |
| Tertiary | `#93c5fd` | `#1e3a5f` |
| Start/Trigger | `#fed7aa` | `#c2410c` |
| End/Success | `#a7f3d0` | `#047857` |
| Warning/Reset | `#fee2e2` | `#dc2626` |
| Decision | `#fef3c7` | `#b45309` |
| AI/LLM | `#ddd6fe` | `#6d28d9` |
| Inactive/Disabled | `#dbeafe` | `#1e40af` (dashed stroke) |
| Error | `#fecaca` | `#b91c1c` |

---

## Text colors (hierarchy)

| Level | Color | Used for |
|---|---|---|
| Title | `#1e40af` | Section heading, major label |
| Subtitle | `#3b82f6` | Subheading, secondary label |
| Body/Detail | `#64748b` | Description, annotation |
| On light fills | `#374151` | Text inside light shapes |
| On dark fills | `#ffffff` | Text inside dark shapes |

---

## Evidence artifact colors

| Artifact | Background | Text color |
|---|---|---|
| Code snippet | `#1e293b` | Syntax-colored |
| JSON/data example | `#1e293b` | `#22c55e` (green) |

---

## Arrow & line colors

| Element | Color |
|---|---|
| Arrow | Stroke color of the source element |
| Structural line | Primary stroke `#1e3a5f` or Slate `#64748b` |
| Marker dot | Primary fill `#3b82f6` |

---

## AWS palette

| Service category | Background | Stroke |
|---|---|---|
| Compute (EC2, Lambda, ECS) | `#ff9900` | `#cc7a00` |
| Storage (S3, EBS) | `#3f8624` | `#2d6119` |
| Database (RDS, DynamoDB) | `#3b48cc` | `#2d3899` |
| Networking (VPC, Route53) | `#8c4fff` | `#6b3dcc` |
| Security (IAM, KMS) | `#dd344c` | `#b12a3d` |
| ML (SageMaker, Bedrock) | `#01a88d` | `#017d69` |

## Azure palette

| Service category | Background | Stroke |
|---|---|---|
| Compute | `#0078d4` | `#005a9e` |
| Storage | `#50e6ff` | `#3cb5cc` |
| Database | `#0078d4` | `#005a9e` |
| Networking | `#773adc` | `#5a2ca8` |
| Security | `#ff8c00` | `#cc7000` |
| AI/ML | `#50e6ff` | `#3cb5cc` |

## GCP palette

| Service category | Background | Stroke |
|---|---|---|
| Compute (GCE, Cloud Run) | `#4285f4` | `#3367d6` |
| Storage (GCS) | `#34a853` | `#2d8e47` |
| Database (Cloud SQL) | `#ea4335` | `#c53929` |
| Networking | `#fbbc04` | `#d99e04` |
| AI/ML (Vertex AI) | `#9334e6` | `#7627b8` |

## Kubernetes palette

| Component | Background | Stroke |
|---|---|---|
| Pod | `#326ce5` | `#2756b8` |
| Service | `#326ce5` | `#2756b8` |
| Deployment | `#326ce5` | `#2756b8` |
| ConfigMap/Secret | `#7f8c8d` | `#626d6e` |
| Ingress | `#00d4aa` | `#00a888` |
| Node | `#303030` | `#1a1a1a` |
| Namespace | `#f0f0f0` | `#c0c0c0` (dashed) |

---

## Background

| Property | Value |
|---|---|
| Canvas background | `#ffffff` |

# Catalog icons — offline OSS brand tiles

The skill ships 8 OSS catalog packs (ported from drawio-ai-kit@bda82a2, MIT) with embedded base64 tiles for offline diagram generation.

## Available packs

| Pack | Icons | Brands (sample) |
|---|---|---|
| observability | 26 | Datadog, Grafana, Prometheus, Jaeger, OpenTelemetry |
| bigdata | 55 | Kafka, Spark, Flink, Hudi, Iceberg, Debezium, Delta |
| database | 66 | PostgreSQL, MySQL, MongoDB, Redis, ClickHouse, Neo4j |
| cicd | 42 | Jenkins, GitHub Actions, ArgoCD, Terraform, Ansible |
| aiml | 26 | MLflow, Kubeflow, PyTorch, TensorFlow |
| containers | 26 | Docker, Kubernetes, Istio, Linkerd |
| databricks | 24 | Databricks One, Delta Sharing, Unity Catalog, Lakehouse |
| network | 16 | Nginx, Envoy, Kong, Traefik |

## How to use

Search for OSS brands through `shapesearch.py` — it merges catalog tiles with the official shape index automatically:

```bash
python3 scripts/shapesearch.py "clickhouse" --json
# → {"title": "ClickHouse", "style": "...image=data:image/png,...", "source": "catalog"}
```

The `--json` output includes a `source` field: `catalog` for OSS pack tiles, `shape-index` for official draw.io stencils.

## Offline guarantee

Catalog tiles embed `data:image/png;base64,...` directly in the style string. No network fetch needed when exporting or previewing — unlike CDN-based brand logos (aiicons.py), catalog icons render offline.

## Fallback: aiicons.py

For AI/LLM brand logos not covered by catalog packs (321 brands from lobe-icons), use `aiicons.py`. This fetches from CDN:
```bash
python3 scripts/aiicons.py "claude" --json      # CDN-referenced
python3 scripts/aiicons.py "openai" --embed     # self-contained data URI
```

## Adding new catalog packs

Use `build_pack.py` to regenerate packs from manifests:
```bash
python3 scripts/build_pack.py mypack
```
Requires `cairosvg` (optional: `pip install cairosvg` for PNG rasterize) and network for devicon/simple-icons CDN fetch. See `packs/MANIFESTS-NOTICE.md` for the manifest schema.

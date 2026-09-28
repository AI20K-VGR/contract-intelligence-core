# Usage — drawio skill examples

## Canonical examples

### Microservices e-commerce

Describe the architecture in natural language and the skill generates a `.drawio` XML with proper container nesting, edge routing, and branding:

> Create a microservices e-commerce architecture with Mobile/Web/Admin
> clients, API Gateway, Auth/User/Order/Product/Payment services, Kafka
> message queue, Notification service, and User DB / Order DB / Product DB
> / Redis Cache / Stripe API.

### Topology: Star

Central message broker with 6 microservices radiating outward. Edges enter from different sides, zero crossings. ~7 nodes.

### Topology: Layered flow

E-commerce with 2 cross-connections (Order→Product same-tier horizontal, Auth→Redis diagonal via routing corridor). 10 nodes, 4 tiers.

### Topology: Ring / cycle

CI/CD pipeline with closed loop + 2 spur branches. Edges flow along the perimeter without crossing the interior. ~8 nodes.

## Codebase visualization

Import graph extraction → auto-layout → validate:
```bash
python3 scripts/pyimports.py   myproject --group -o graph.json
python3 scripts/jsimports.py   ./src     --group -o graph.json
python3 scripts/goimports.py   ./module  --group -o graph.json
python3 scripts/rustimports.py ./crate   --group -o graph.json
python3 scripts/pyclasses.py   mypackage --group -o graph.json
python3 scripts/autolayout.py  graph.json -o diagram.drawio
```

## Shape search

10,000+ official draw.io stencils + OSS catalog tiles (offline):
```bash
python3 scripts/shapesearch.py "aws lambda" --limit 5
```

## AI/LLM brand logos

321 logos (OpenAI, Claude, Gemini, Mistral, Llama, Ollama, LangChain…) from lobe-icons (MIT):
```bash
python3 scripts/aiicons.py "claude" --json
```

## Topology-aware edge routing

When generating diagrams with 3+ components, route edges through dedicated corridors between shape tiers, avoiding shape crossings. Pin entry/exit points at shape edges; distribute parallel edges to different sides. For hub-centric topologies, center the hub and radiate edges outward (don't snake through gaps).

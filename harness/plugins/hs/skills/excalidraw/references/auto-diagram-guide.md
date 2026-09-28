# Auto-diagram: zero-config codebase visualization

Analyze any codebase, auto-generate an architecture diagram — no description needed; read code, determine what to draw.

## Context budget (hard constraints)

| Operation | Limit |
|---|---|
| Grep results/pattern | 20 results |
| Files read per component | 5 files |
| Tool calls Phase 2 | 15 |
| Tool calls Phase 3 | 10 |

If the limit is exceeded: continue with partial results, note the gap.

---

## Phase 1: Project detection

1. **Read root files**: `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, `Gemfile`, `Makefile`, `Dockerfile`, `docker-compose.yml`, `*.tf`
2. **Scan directory structure**: `ls` root and first-level subdirs
3. **Detect project type**:
   - **Monorepo**: `workspaces` in package.json, `lerna.json`, `pnpm-workspace.yaml`, `packages/` or `apps/`
   - **Microservices**: multiple Dockerfiles, docker-compose with 3+ services
   - **Standard app**: single service with standard dirs
4. **Detect framework**:
   - React/Next.js: `next.config.*`, `src/app/`, `src/pages/`
   - Express/Fastify/Hono: `routes/`, `controllers/`, `middleware/`
   - Django/Flask/FastAPI: `manage.py`, `wsgi.py`, `app.py`, `main.py` + `uvicorn`
   - Go: `cmd/`, `internal/`, `pkg/`

**Monorepo**: scope to package-level view first. One box per package. Offer drill-down.

---

## Phase 2: Component discovery (max 15 tool calls)

### Web applications
1. **Frontend**: Glob `*.tsx`, `*.jsx`, `*.vue`, `*.svelte` in `src/`, `app/`, `pages/`
2. **API routes**: Grep `router\.(get|post|put|delete)`, `@(Get|Post|Put|Delete)`, `@app\.route`
3. **Database**: Find `prisma/schema.prisma`, `models.py`, `*.entity.ts`, `migrations/`
4. **External services**: Grep `axios`, `fetch(`, `requests\.`, `http\.NewRequest`
5. **Message queues**: Grep `amqp`, `kafka`, `bull`, `celery`, `SQS`, `pubsub`
6. **Cache**: Grep `redis`, `memcached`, `cache` in imports
7. **Auth**: Grep `passport`, `jwt`, `oauth`, `@Auth`, `middleware.*auth`

### Infrastructure
1. Read `docker-compose.yml` service definitions
2. Grep `*.tf` for `resource "` blocks
3. Glob `**/k8s/*.yaml` or `**/manifests/*.yaml`

### Libraries / CLIs
1. Find `main`, `bin`, `exports` in package config
2. Map public API surface
3. Read dependency list

**Output**: 4-12 components with name, type, key files.

---

## Phase 3: Connection mapping (max 10 tool calls)

1. **Read entry points** (up to 5 files). Look for:
   - Import statements referencing OTHER components
   - HTTP client calls, RPC calls, queue publishers
   - Database queries
   - Event emitter/listener

2. **Classify connections**:
   - `REST/HTTP`, `SQL/ORM`, `gRPC/RPC`, `Event/Queue`, `Import`

3. **Build edge list**: `ComponentA --[protocol]--> ComponentB`

If a connection is unclear: display the component without an arrow, note it for the user.

---

## Phase 4: Verify with user

Present a summary BEFORE drawing:

> "I found **N components** and **M connections**:
>
> **Components:** [list with types]
> **Connections:** [edge list]
>
> Is this correct? Anything to add, remove, or rename?"

Wait for confirmation.

---

## Phase 5: Layout selection

| Pattern | Layout | Trigger |
|---|---|---|
| Request/response (standard web app) | Vertical flow | Frontend + API + DB detected |
| Data pipeline / ETL | Horizontal pipeline | Linear transform chain |
| Event-driven / microservices | Hub and spoke | Message broker detected |
| Monolith with modules | Vertical flow + zones | Single service, multiple modules |

Default: vertical flow. Hybrid: vertical with event bus in the middle layer.

---

## Phase 6: Generate diagram

Use file-based mode (`.excalidraw` file); follow sizing rules (`references/visual-specs.md`) + color palette (SKILL.md).

**Label format** for each box:
```
ComponentName
tech-stack
(key detail)
```

---

## Constraints

- Max 12 components per diagram — group if exceeded
- Max 20 arrows — primary data flow only, secondary uses dashed
- Always include title: `{ProjectName} Architecture Overview`
- Include legend if using > 3 colors

## Grouping (> 12 components)

1. Group by top-level directory
2. If a directory has > 3 components, collapse into a zone
3. Display zone as a dashed rectangle with a summary box
4. Offer drill-down

## Edge cases

| Situation | Handling |
|---|---|
| Empty repo (< 5 files) | Simple module diagram |
| Monorepo | Package-level view, offer drill-down |
| Architecture unclear | File dependency graph |
| Connection not detectable | Component without arrow, note for user |
| Specific subdirectory given | Scope analysis to that directory |
| Context budget exceeded | Partial results, tell user what was omitted |

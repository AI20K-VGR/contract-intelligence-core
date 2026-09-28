# Mermaid.js v11 -- Diagram types reference

Full syntax for 24+ diagram types in Mermaid.js v11.

## Core diagrams

### Flowchart
Process flows, decision trees, workflows.

```
flowchart {direction}
  {nodeId}[{label}] {arrow} {nodeId}[{label}]
```

**Directions:** `TB`/`TD` (top→bottom), `BT`, `LR` (left→right), `RL`
**Shapes:** `()` round, `[]` rect, `{}` diamond, `{{}}` hexagon, `(())` circle
**Arrows:** `-->` solid, `-.->` dotted, `==>` thick
**Label on arrow:** `-->|text|`
**Subgraph:**
```
subgraph Title
  A --> B
end
```

### Sequence Diagram
Actor interactions, API flows, message sequences.

```
sequenceDiagram
  participant A as Actor
  A->>B: Message
  activate B
  B-->>A: Response
  deactivate B
```

**Arrows:** `->` solid open, `->>` arrowhead, `-->` dotted, `-x` cross, `-)` async
**Control blocks:** `loop`, `alt`/`else`, `opt`, `par`/`and`, `critical`, `break`
```
loop Every minute
  A->>B: Heartbeat
end
alt Success
  A->>B: Path 1
else
  A->>B: Path 2
end
```

### Class Diagram
OOP structures, inheritance, relationships.

```
classDiagram
  class Animal {
    +String name
    -int age
    #bool active
    +void eat()
    -int count()$
  }
  Animal <|-- Dog : inherits
```

**Visibility:** `+` public, `-` private, `#` protected, `~` package
**Modifiers:** `$` static, `*` abstract
**Relationships:** `<|--` inherit, `*--` compose, `o--` aggregate, `-->` associate, `..>` depend, `..|>` realize

### State Diagram
State machines, transitions, workflows.

```
stateDiagram-v2
  [*] --> Idle
  Idle --> Running : start
  Running --> Idle : stop
  Running --> [*] : done

  state Running {
    [*] --> Processing
    Processing --> Done
  }
```

**Features:** Composite states, choice `<<choice>>`, fork/join `<<fork>>`/`<<join>>`, concurrency (`--`)

### ER Diagram
Database relationships, schemas.

```
erDiagram
  CUSTOMER ||--o{ ORDER : places
  CUSTOMER {
    int id PK
    string email
    string name
  }
  ORDER ||--|{ LINE_ITEM : contains
```

**Cardinality:** `||` one, `|o` zero-or-one, `}|` one-or-many, `}o` zero-or-many

## Planning diagrams

### Gantt chart
Project timelines, sprint schedules.

```
gantt
  title Sprint
  dateFormat YYYY-MM-DD
  section Backend
    API       :done, api, 2024-01-01, 3d
    DB Mig    :active, db, after api, 2d
    Tests     :test, after db, 2d
  section Frontend
    UI        :done, ui, 2024-01-01, 4d
    Milestone :milestone, m1, 2024-01-07, 0d
```

**Status tags:** `done`, `active`, `crit`, `milestone`

### User Journey
Experience flows with satisfaction scores.

```
journey
  title Onboarding
  section Signup
    Visit site: 3: Customer
    Create account: 2: Customer
    Email verify: 4: Customer, System
```

**Scores:** 1–5 satisfaction levels per step.

### Kanban / quadrant chart
```
kanban
  Todo[Backlog]
    task1[Implement API]
    @{ assigned: "Dev", priority: "High" }
  InProgress[In Progress]
    task2[Fix bug]
```

```
quadrantChart
  x-axis Low Effort --> High Effort
  y-axis Low Impact --> High Impact
  Feature A: [0.3, 0.7]
```

## Architecture diagrams

### Architecture diagram (cloud infra)

```
architecture-beta
  group vpc(cloud)[VPC]
  service api(server)[API] in vpc
  service db(database)[Database] in vpc
  api:R --> L:db
```

**Icons:** `cloud`, `database`, `disk`, `internet`, `server`; iconify packs via `registerIconPacks()`
**Port directions:** `:T`, `:B`, `:L`, `:R`

### C4 Diagram
System-level architecture (Context, Container, Component, Dynamic).

```
C4Context
  Person(user, "User", "End user")
  System(app, "Web App", "Delivers content")
  System_Ext(email, "Email System")
  Rel(user, app, "Uses")
  Rel(app, email, "Sends via")
```

### Block Diagram
```
block-beta
  columns 3
  A["Service A"] B["Service B"] C["Service C"]
  A --> B --> C
```
Shapes: `rounded`, `stadium`, `cylinder`, `diamond`, `trapezoid`, `hexagon`

## Data visualization

### Pie chart

```
pie showData
  title Traffic Sources
  "Organic" : 45.5
  "Direct"  : 25.3
  "Social"  : 15.8
```

### XY chart (bar + line)

```
xychart-beta
  x-axis [jan, feb, mar, apr]
  y-axis "Revenue" 0 --> 100
  bar  [25, 40, 55, 70]
  line [20, 35, 50, 65]
```

### Sankey diagram
Flow / resource allocation visualization.

```
sankey-beta
  Source,Target,Value
  Traffic,Organic,45
  Traffic,Paid,30
  Organic,Converted,20
```

### Radar Chart
```
radar-beta
  axis Frontend, Backend, DevOps, Testing
  curve Alice{5, 3, 2, 4}
  curve Bob{3, 5, 4, 3}
```

### Treemap
```
treemap-beta
  "Root"
    "Category A"
      "Item 1": 100
      "Item 2": 200
```

## Technical diagrams

### Git graph
```
gitGraph
  commit
  branch develop
  checkout develop
  commit
  branch feature/auth
  checkout feature/auth
  commit
  checkout develop
  merge feature/auth
  checkout main
  merge develop tag: "v1.0.0"
```

### Timeline
```
timeline
  2023 : First release : Beta launch
  2024 : GA launch     : 10k users
```

### Mindmap
```
mindmap
  root((Central Idea))
    Branch A
      Sub A1
    Branch B
```

### Niche types
- `packet-beta` — network protocol byte structures
- `zenuml` — alternative sequence syntax (method-call style)
- `requirementDiagram` — SysML requirements + traceability

## Quick reference table

| Type | Best For | Keyword |
|------|----------|---------|
| `flowchart` | Processes, decisions | `flowchart TD` |
| `sequenceDiagram` | API flows, messages | `sequenceDiagram` |
| `classDiagram` | OOP, data models | `classDiagram` |
| `stateDiagram-v2` | State machines | `stateDiagram-v2` |
| `erDiagram` | DB schemas | `erDiagram` |
| `gantt` | Timelines, sprints | `gantt` |
| `journey` | UX flows | `journey` |
| `architecture-beta` | Cloud infra | `architecture-beta` |
| `C4Context` | System architecture | `C4Context` |
| `gitGraph` | Branching | `gitGraph` |
| `pie` | Proportions | `pie showData` |
| `mindmap` | Hierarchy | `mindmap` |
| `timeline` | Chronology | `timeline` |
| `xychart-beta` | Trends, bar+line | `xychart-beta` |

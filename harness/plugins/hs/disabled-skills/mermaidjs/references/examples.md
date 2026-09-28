# Mermaid.js v11 -- Practical examples

Practical patterns for common documentation scenarios.

## Software Architecture

**Microservices:**
```mermaid
flowchart TB
  Client[Web Client]
  Gateway[API Gateway]
  Auth[Auth Service]
  User[User Service]
  Order[Order Service]
  DB1[(Users DB)]
  DB2[(Orders DB)]
  Cache[(Redis)]

  Client --> Gateway
  Gateway --> Auth
  Gateway --> User
  Gateway --> Order
  User --> DB1
  Order --> DB2
  User --> Cache
```

**C4 System Context:**
```mermaid
C4Context
  Person(customer, "Customer", "End user")
  System(app, "Web Application", "Delivers content")
  System_Ext(email, "Email System", "Sends notifications")

  Rel(customer, app, "Uses")
  Rel(app, email, "Sends via")
```

**Cloud Infrastructure:**
```mermaid
architecture-beta
  group vpc(cloud)[VPC]
  group public(cloud)[Public Subnet] in vpc
  group private(cloud)[Private Subnet] in vpc

  service lb(internet)[Load Balancer] in public
  service web(server)[Web Servers] in public
  service api(server)[API Servers] in private
  service db(database)[RDS] in private
  service cache(disk)[ElastiCache] in private

  lb:B --> T:web
  web:B --> T:api
  api:R --> L:db
  api:R --> L:cache
```

## API Documentation

**Authentication Flow:**
```mermaid
sequenceDiagram
  participant C as Client
  participant A as API
  participant D as Database

  C->>A: POST /auth/login
  activate A
  A->>D: Verify credentials
  D-->>A: User found
  A->>A: Generate JWT
  A-->>C: 200 OK + token
  deactivate A

  C->>A: GET /protected (Bearer token)
  activate A
  A->>A: Validate JWT
  A->>D: Fetch data
  D-->>A: Data
  A-->>C: 200 OK + data
  deactivate A
```

**REST Endpoint Map:**
```mermaid
flowchart LR
  API[API]
  Users[/users]
  Posts[/posts]

  API --> Users
  API --> Posts

  Users --> U1[GET /users]
  Users --> U2[POST /users]
  Users --> U3[GET /users/:id]
  Users --> U4[PUT /users/:id]
  Users --> U5[DELETE /users/:id]
```

## Database Design

**E-Commerce Schema:**
```mermaid
erDiagram
  CUSTOMER ||--o{ ORDER : places
  CUSTOMER {
    int id PK
    string email
    string name
  }
  ORDER ||--|{ LINE_ITEM : contains
  ORDER {
    int id PK
    int customer_id FK
    date created_at
    string status
  }
  PRODUCT ||--o{ LINE_ITEM : includes
  PRODUCT {
    int id PK
    string name
    decimal price
  }
  LINE_ITEM {
    int order_id FK
    int product_id FK
    int quantity
    decimal unit_price
  }
```

## State Machines

**Order Processing:**
```mermaid
stateDiagram-v2
  [*] --> Pending
  Pending --> Processing : payment_received
  Pending --> Cancelled : timeout
  Processing --> Shipped : items_packed
  Processing --> Failed : error
  Shipped --> Delivered : confirmed
  Delivered --> [*]
  Failed --> Refunded : refund_processed
  Cancelled --> [*]
  Refunded --> [*]
```

**Auth States:**
```mermaid
stateDiagram-v2
  [*] --> LoggedOut
  LoggedOut --> LoggingIn : submit_credentials
  LoggingIn --> LoggedIn : success
  LoggingIn --> LoggedOut : failure
  LoggedIn --> VerifyingMFA : requires_2fa
  VerifyingMFA --> LoggedIn : mfa_success
  VerifyingMFA --> LoggedOut : mfa_failure
  LoggedIn --> LoggedOut : logout
```

## Project Planning

**Sprint Timeline:**
```mermaid
gantt
  title Sprint 12 (2 weeks)
  dateFormat YYYY-MM-DD
  section Backend
    API endpoints     :done, api, 2024-01-01, 3d
    Database migration:active, db, after api, 2d
    Testing           :test, after db, 2d
  section Frontend
    UI components     :done, ui, 2024-01-01, 4d
    Integration       :active, int, after ui, 3d
  section DevOps
    CI/CD setup       :crit, cicd, 2024-01-06, 2d
    Deployment        :milestone, deploy, after cicd, 1d
```

## Object-Oriented Design

**Payment System:**
```mermaid
classDiagram
  class PaymentProcessor {
    <<interface>>
    +processPayment(amount)
    +refund(transactionId)
  }
  class StripeProcessor {
    -apiKey: string
    +processPayment(amount)
    +refund(transactionId)
  }
  class PaymentService {
    -processor: PaymentProcessor
    +charge(customer, amount)
    +issueRefund(orderId)
  }

  PaymentProcessor <|.. StripeProcessor
  PaymentService --> PaymentProcessor
```

## CI/CD Pipeline

**Deployment Flow:**
```mermaid
flowchart LR
  Code[Push Code] --> CI{CI Checks}
  CI -->|Pass| Build[Build]
  CI -->|Fail| Notify[Notify Team]
  Build --> Test[Run Tests]
  Test -->|Pass| Stage[Deploy Staging]
  Test -->|Fail| Notify
  Stage --> Gate{Manual Approval}
  Gate -->|Approved| Prod[Deploy Production]
  Gate -->|Rejected| End[End]
  Prod --> Monitor[Monitor]
```

**Git Branching Strategy:**
```mermaid
gitGraph
  commit
  branch develop
  checkout develop
  commit
  branch feature/auth
  checkout feature/auth
  commit
  commit
  checkout develop
  merge feature/auth
  checkout main
  merge develop tag: "v1.0.0"
  checkout develop
  branch feature/payments
  checkout feature/payments
  commit
  checkout develop
  merge feature/payments
  checkout main
  merge develop tag: "v1.1.0"
```

## Data Visualization

**Traffic Sources (Pie):**
```mermaid
pie showData
  title Traffic Sources Q4
  "Organic Search" : 45.5
  "Direct"         : 25.3
  "Social Media"   : 15.8
  "Referral"       : 8.4
  "Paid Ads"       : 5.0
```

**Team Skills (Radar):**
```mermaid
radar-beta
  axis Frontend, Backend, DevOps, Testing, Design
  curve Alice{5, 3, 2, 4, 2}
  curve Bob{3, 5, 4, 3, 1}
```

## Styling Tips

**Per-diagram theme via frontmatter:**
````markdown
```mermaid
---
theme: dark
---
flowchart TD
  A --> B
```
````

**Inline init block** (highest priority, overrides global):
```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#ff6347'}}}%%
flowchart TD
  classDef hot fill:#f96,stroke:#333,stroke-width:2px
  A[Critical Path]:::hot --> B[Next Step]
```

**Naming conventions:**
- Descriptive node IDs: `userService` not `A`
- Clear labels: `[User Service]` not `[US]`
- Labelled edges: `-->|authenticates|` not `-->`
- Security: use `securityLevel: 'strict'` for user-generated diagrams (prevents XSS)

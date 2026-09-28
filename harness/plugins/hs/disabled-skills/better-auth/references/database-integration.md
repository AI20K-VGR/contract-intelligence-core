# Database Integration

Supports multiple databases/ORMs for flexible persistence.

## Supported Databases

- SQLite
- PostgreSQL
- MySQL/MariaDB
- MongoDB
- Any database with adapter support

## Direct Database Connection

### SQLite

```ts
import { betterAuth } from "better-auth";
import Database from "better-sqlite3";

export const auth = betterAuth({
  database: new Database("./sqlite.db"),
  // or
  database: new Database(":memory:") // In-memory for testing
});
```

### PostgreSQL

```ts
import { betterAuth } from "better-auth";
import { Pool } from "pg";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  // or explicit config
  host: "localhost",
  port: 5432,
  user: "postgres",
  password: "password",
  database: "myapp"
});

export const auth = betterAuth({
  database: pool
});
```

### MySQL

```ts
import { betterAuth } from "better-auth";
import { createPool } from "mysql2/promise";

const pool = createPool({
  host: "localhost",
  user: "root",
  password: "password",
  database: "myapp",
  waitForConnections: true,
  connectionLimit: 10
});

export const auth = betterAuth({
  database: pool
});
```

## ORM Adapters

### Drizzle ORM

**Install:**
```bash
npm install drizzle-orm better-auth
```

**Setup:**
```ts
import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL
});

const db = drizzle(pool);

export const auth = betterAuth({
  database: drizzleAdapter(db, {
    provider: "pg", // "pg" | "mysql" | "sqlite"
    schema: {
      // Optional: custom table names
      user: "users",
      session: "sessions",
      account: "accounts",
      verification: "verifications"
    }
  })
});
```

**Generate Schema:**
```bash
npx @better-auth/cli generate --adapter drizzle
```

### Prisma

**Install:**
```bash
npm install @prisma/client better-auth
```

**Setup:**
```ts
import { betterAuth } from "better-auth";
import { prismaAdapter } from "better-auth/adapters/prisma";
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

export const auth = betterAuth({
  database: prismaAdapter(prisma, {
    provider: "postgresql", // "postgresql" | "mysql" | "sqlite"
  })
});
```

**Generate Schema:**
```bash
npx @better-auth/cli generate --adapter prisma
```

**Apply to Prisma:**
```bash
# Add generated schema to schema.prisma
npx prisma migrate dev --name init
npx prisma generate
```

### Kysely

**Install:**
```bash
npm install kysely better-auth
```

**Setup:**
```ts
import { betterAuth } from "better-auth";
import { kyselyAdapter } from "better-auth/adapters/kysely";
import { Kysely, PostgresDialect } from "kysely";
import { Pool } from "pg";

const db = new Kysely({
  dialect: new PostgresDialect({
    pool: new Pool({
      connectionString: process.env.DATABASE_URL
    })
  })
});

export const auth = betterAuth({
  database: kyselyAdapter(db, {
    provider: "pg"
  })
});
```

**Auto-migrate with Kysely:**
```bash
npx @better-auth/cli migrate --adapter kysely
```

### MongoDB

**Install:**
```bash
npm install mongodb better-auth
```

**Setup:**
```ts
import { betterAuth } from "better-auth";
import { mongodbAdapter } from "better-auth/adapters/mongodb";
import { MongoClient } from "mongodb";

const client = new MongoClient(process.env.MONGODB_URI!);
await client.connect();

export const auth = betterAuth({
  database: mongodbAdapter(client, {
    databaseName: "myapp"
  })
});
```

**Generate Collections:**
```bash
npx @better-auth/cli generate --adapter mongodb
```

## Core Database Schema

Core tables/collections required:

### User Table

```sql
CREATE TABLE user (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  emailVerified BOOLEAN DEFAULT FALSE,
  name TEXT,
  image TEXT,
  createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Session Table

```sql
CREATE TABLE session (
  id TEXT PRIMARY KEY,
  userId TEXT NOT NULL,
  expiresAt TIMESTAMP NOT NULL,
  ipAddress TEXT,
  userAgent TEXT,
  createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (userId) REFERENCES user(id) ON DELETE CASCADE
);
```

### Account Table

```sql
CREATE TABLE account (
  id TEXT PRIMARY KEY,
  userId TEXT NOT NULL,
  accountId TEXT NOT NULL,
  providerId TEXT NOT NULL,
  accessToken TEXT,
  refreshToken TEXT,
  expiresAt TIMESTAMP,
  scope TEXT,
  createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (userId) REFERENCES user(id) ON DELETE CASCADE,
  UNIQUE(providerId, accountId)
);
```

### Verification Table

```sql
CREATE TABLE verification (
  id TEXT PRIMARY KEY,
  identifier TEXT NOT NULL,
  value TEXT NOT NULL,
  expiresAt TIMESTAMP NOT NULL,
  createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```


---

Continued in [database-integration-cont.md](database-integration-cont.md)

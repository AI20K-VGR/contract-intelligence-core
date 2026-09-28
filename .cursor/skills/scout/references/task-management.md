# Scout — Parallel task management

Track scout agent progress using TaskCreate/TaskUpdate/TaskList.

## When to create tasks

| Agent count | Create tasks? | Reason |
|---|---|---|
| ≤ 2 | No | Overhead not worth it, completes quickly |
| ≥ 3 | Yes | Need to track parallel progress |

## Registration flow

```
TaskList()                         // check for existing scout tasks
  → Already exist? → Reuse, do not recreate
  → Empty?         → TaskCreate per agent
```

## Metadata schema

```
TaskCreate(
  subject: "Scout {directory} for {target}",
  activeForm: "Scouting {directory}",
  description: "Find {pattern} in {scope}",
  metadata: {
    agentType: "Explore",          // "Explore" (internal) or "Bash" (external)
    scope: "harness/hooks/,harness/scripts/",
    scale: 6,
    agentIndex: 1,                 // 1-indexed position
    totalAgents: 6,
    toolMode: "internal",          // "internal" or "external"
    effort: "3m"                   // fixed timeout per agent
  }
)
```

### Required fields

- `agentType` — subagent type: `"Explore"` (internal) or `"Bash"` (external)
- `scope` — directory boundary for this agent (comma-separated)
- `scale` — total SCALE determined in step 1
- `agentIndex` / `totalAgents` — position within the agent set
- `toolMode` — `"internal"` or `"external"`
- `effort` — always `"3m"`

### Optional fields

- `searchPatterns` — patterns being searched (aids debugging)
- `externalTool` — if external: `"gemini"`, `"agy"`, or `"opencode"`

## Task lifecycle

```
Step 3: TaskCreate per agent       → status: pending
Step 4: Before spawning agent      → TaskUpdate → status: in_progress
Step 5: Agent returns report       → TaskUpdate → status: completed
Step 5: Agent times out (3 min)    → keep in_progress, add metadata.error: "timeout"
```

### Timeout handling

```
TaskUpdate(taskId, {
  metadata: { ...existing, error: "timeout" }
})
// Task stays in_progress — distinguishes timeout from still-running
// Record in the "Open questions" section of the report
```

## Example — Internal scout (SCALE=6)

```
TaskCreate(subject: "Scout harness/hooks/ for gate scripts",
  activeForm: "Scouting harness/hooks/",
  metadata: { agentType: "Explore", scope: "harness/hooks/", scale: 6,
              agentIndex: 1, totalAgents: 6, toolMode: "internal", effort: "3m" })

// Repeat for agents 2-6 with different scopes

// Spawn all in a single message → true parallelism
TaskUpdate(taskId1, { status: "in_progress" })
// ...

// After receiving results
TaskUpdate(taskId1, { status: "completed" })
TaskUpdate(taskId3, { metadata: { error: "timeout" } })  // agent 3 timed out
```

## Integration with cook/plan

Scout tasks are **independent** of cook/plan tasks — not parent-child. Scout finishes first; cook hydrates phase tasks separately afterward.

## TaskCreate error handling

If TaskCreate fails → log a warning, continue scouting without task tracking (observability only, non-blocking).

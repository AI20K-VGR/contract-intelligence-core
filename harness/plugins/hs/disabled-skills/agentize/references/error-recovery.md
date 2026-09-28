# agentize — error recovery (failure mode → action)

When a step in the agentize workflow hits one of these, take the action and continue (or stop cleanly) rather than forcing the full CLI+MCP shape:

- **Scout returns nothing exposable** → stop; suggest refactoring the target first.
- **Core cannot be extracted (circular deps)** → scope down to one module, ship that.
- **Target is browser-only** → drop `--cli`; ship `--mcp` with Streamable HTTP.
- **No side-effects or data** → drop `--mcp`; ship `--cli` only.
- **Credential design is unclear in `--auto`** → switch that axis to `--ask`.

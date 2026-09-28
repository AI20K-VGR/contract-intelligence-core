# LLM-CLI Integration Guide (gemini primary for headless/CI, agy independent path)

The LLM-driven path of `/hs:use-mcp` runs an external CLI that reads MCP servers and picks tools from natural language. Two CLIs are supported:

1. **`gemini` CLI + `GEMINI_API_KEY` (PRIMARY for headless/CI).** On 2026-06-18 Google discontinued the *consumer OAuth tiers* of the `gemini` CLI (free / AI Pro / Ultra login). **API-key auth was not affected** — `gemini` keyed with `GEMINI_API_KEY` (AI Studio / Code Assist) keeps serving requests, runs fully headless. Use this path for automated/CI/unattended runs.
2. **`agy` (Antigravity) CLI (independent OAuth/Antigravity path).** Google's successor CLI, on its own path — not a fallback bolted onto `gemini`. OAuth-primary: headless API-key path unusable today (upstream `antigravity-cli#78`) — needs interactive sign-in, not runnable purely from an env key.
   Reach for it for interactive or Antigravity-workspace use; `gemini` stays primary for headless/CI — full detail in **agy-MCP (independent path)** below.
3. **Deterministic Path-2 scripts** (`cli.ts`) when neither CLI is available.

Both CLIs accept the same `gemini-*` model ids and have no auto-loaded system-prompt file, so `/hs:use-mcp` prepends the JSON proxy contract (`references/mcp-proxy-contract.md`) into the piped prompt.

## Authentication

```bash
# PRIMARY — headless, key-based, unaffected by the 2026-06-18 consumer-tier change.
export GEMINI_API_KEY="your-ai-studio-key"   # https://aistudio.google.com/apikey

# FALLBACK — agy uses interactive OAuth; sign in once, no env key path.
agy   # launch with no args to sign in (only if you must use agy)
```

## Model Configuration

Model ids are **not hardcoded** — they live in one file, `data/models.yaml`, resolved by `scripts/resolve_model.py`:

```bash
MODEL=$(python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/resolve_model.py)            # default (env $GEMINI_MODEL overrides)
MODEL=$(python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/resolve_model.py --fallback) # second choice on failure
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/resolve_model.py --list              # available list → LLM picks on total failure
```

Resolution order: `default` → `fallback` → hand `available` to the LLM to pick. `$GEMINI_MODEL` overrides `default` at runtime. Both CLIs accept every `gemini-*` id. To retune models, edit `data/models.yaml` only — never a skill file.

## Installation

```bash
# gemini CLI (primary)
which gemini && gemini --version

# agy CLI (fallback) — only if you need the OAuth path
curl -fsSL https://antigravity.google/cli/install.sh | bash
which agy && agy --version
```

If a binary is not on `PATH` after install it is typically under `~/.local/bin/`. If both pings fail, use Path 2 (the deterministic `cli.ts` scripts).

## MCP Configuration

Both CLIs load MCP servers from the global `~/.gemini/config/mcp_config.json` in print (headless) mode (they do **not** read `.gemini/settings.json`). The file shape matches `.claude/.mcp.json` (`{"mcpServers": {...}}`), so the project's servers are merged into the global file:

```bash
GLOBAL=~/.gemini/config/mcp_config.json
mkdir -p ~/.gemini/config
[ -f "$GLOBAL" ] || echo '{"mcpServers":{}}' > "$GLOBAL"
node -e '
  const fs=require("fs"),os=require("os"),path=require("path");
  const g=path.join(os.homedir(),".gemini/config/mcp_config.json");
  const proj=JSON.parse(fs.readFileSync(".claude/.mcp.json","utf8"));
  const cur=JSON.parse(fs.readFileSync(g,"utf8"));
  cur.mcpServers={...(cur.mcpServers||{}),...(proj.mcpServers||{})};
  fs.writeFileSync(g,JSON.stringify(cur,null,2));
  console.log("merged servers:",Object.keys(cur.mcpServers).join(", "));
'
```

A server entry uses the standard MCP shape:

```json
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "env": {}
    }
  }
}
```

Use `$VAR_NAME` in `env` values for secrets (e.g. `"BRAVE_API_KEY": "$BRAVE_API_KEY"`). Keep `~/.gemini/config/mcp_config.json` out of version control if it holds secrets.

## agy-MCP (independent path)

`agy` is a self-contained path, not a fallback bolted onto `gemini`. Reach for it when the work is interactive or runs inside an Antigravity workspace; `gemini` + `GEMINI_API_KEY` stays the primary for headless/CI (above). Two facts differ from `gemini` and bite if missed:

**Context file — `AGENTS.md`, not `GEMINI.md`.** `agy` auto-loads `AGENTS.md` from the workspace root as its context/instructions file (the Antigravity convention), whereas the retired `gemini` consumer path loaded `GEMINI.md`. Running `agy` from a project that ships an `AGENTS.md` therefore changes what it sees — read that file before you trust an `agy` run.

**Empty MCP config — populate it first.** The global `~/.gemini/config/mcp_config.json` is empty by default (a zero-byte file on a fresh machine). `agy` sees no MCP servers until you merge your project's `.claude/.mcp.json` into it (the same merge as the MCP Configuration section above). Do not assume "agy MCP just works" — verify with a server-name listing first.

**Quickstart (independent path):**

```bash
# 1. Sign in once (OAuth; no env-key headless path — antigravity-cli#78)
agy                       # launch with no args to authenticate

# 2. Populate MCP servers (empty by default — run the merge from MCP Configuration above)

# 3. Run a task (headless print mode, after sign-in)
MODEL=$(python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/resolve_model.py)
printf '%s\n\nTASK: %s' "$CONTRACT" "<task>" \
  | agy --dangerously-skip-permissions --model "$MODEL" -p

# 4. Verify MCP is visible
echo "List the MCP server names available to you. Return ONLY a JSON array." \
  | agy --dangerously-skip-permissions --model "$MODEL" -p
```

## Usage

### Print mode + prepended contract (MCP tasks)

```bash
# PRIMARY: gemini + GEMINI_API_KEY (headless)
printf '%s\n\nTASK: %s' "$CONTRACT" "<task>" \
  | gemini -y -m "$MODEL" -p

# FALLBACK: agy (requires prior interactive OAuth sign-in)
printf '%s\n\nTASK: %s' "$CONTRACT" "<task>" \
  | agy --dangerously-skip-permissions --model "$MODEL" -p
```

### Essential flags

**gemini (primary):**
- `-y` / `--yolo` — auto-approve all tool permission requests (headless mode).
- `-m <id>` / `--model <id>` — model selection; get `<id>` from `resolve_model.py` (see Model Configuration), never hardcode it.
- `-p` / `--prompt` — run a single prompt non-interactively and print the response.

**agy (fallback):**
- `--dangerously-skip-permissions` — the agy equivalent of `gemini -y` / `--yolo`.
- `--model <id>` — same `gemini-*` ids.
- `-p` / `--print` / `--prompt` — headless single-prompt run.
- `--print-timeout <dur>` — native print-mode timeout (default `5m0s`).

### Inline vs stdin

Both forms work in print mode; stdin is preferred when prepending the multi-line contract:

```bash
# Inline (primary)
gemini -y -m "$MODEL" -p "<task>"

# Stdin (primary, preferred for the contract)
printf '%s\n\nTASK: %s' "$CONTRACT" "<task>" | gemini -y -m "$MODEL" -p
```

## Error Handling (structured-error fallback)

Check exit code and output for known error markers. On a `gemini` failure, fall through to `agy`; if `agy` is unavailable or also fails, fall through to Path 2:

```bash
RESULT=$(printf '%s\n\nTASK: %s' "$CONTRACT" "task" | gemini -y -m "$MODEL" -p 2>&1)
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ] || echo "$RESULT" | grep -q "GaxiosError\|RESOURCE_EXHAUSTED\|MODEL_CAPACITY_EXHAUSTED\|PERMISSION_DENIED\|UNAUTHENTICATED"; then
  # 1) try agy (if signed in), else 2) Path 2 deterministic scripts
  RESULT=$(printf '%s\n\nTASK: %s' "$CONTRACT" "task" | agy --dangerously-skip-permissions --model "$MODEL" -p 2>&1) \
    || echo "[LLM_CLI_UNAVAILABLE] Falling back to Path 2 (cli.ts call-tool <server> <tool> '<json>')."
fi
echo "$RESULT"
```

Common failure modes:
- **429 `MODEL_CAPACITY_EXHAUSTED`**: model overloaded. Wait and retry, or switch path — do not downgrade the model.
- **429 `RESOURCE_EXHAUSTED`**: rate limit. Wait and retry, or switch to scripts.
- **403 `PERMISSION_DENIED`**: account tier / key doesn't support the model.
- **401 `UNAUTHENTICATED`**: `GEMINI_API_KEY` missing/invalid (gemini), or agy token expired — for agy, re-run `agy` with no arguments to sign in.
- **Timeout**: print-mode wait exceeded. Reduce prompt complexity or switch model.

## Verifying MCP is loaded

```bash
echo "List the MCP server names available to you. Return ONLY a JSON array of names." \
  | gemini -y -m "$MODEL" -p
```

If the array is empty, confirm `~/.gemini/config/mcp_config.json` has your servers and that `GEMINI_API_KEY` is exported (or agy is signed in).

## Comparison with Alternatives

| Method | Auth | Headless | Best For |
|--------|------|----------|----------|
| gemini CLI + `GEMINI_API_KEY` | API key | yes | Primary — automated / CI / unattended |
| agy CLI | OAuth | needs sign-in | Fallback when gemini is unavailable |
| Direct Scripts (`cli.ts`) | none | yes | Deterministic invocation, no LLM |

**Recommendation**: use `gemini` + `GEMINI_API_KEY` as the primary headless method, fall back to `agy` (OAuth) if needed, then to `cli.ts call-tool` (Path 2).

## Resources

- [Google AI Studio API key](https://aistudio.google.com/apikey)
- [Antigravity CLI install](https://antigravity.google/cli/install.sh)
- `references/configuration.md` — `.mcp.json` schema, env file lookup order
- `references/mcp-protocol.md` — JSON-RPC details, transports, error codes
- `references/mcp-proxy-contract.md` — the JSON contract `/hs:use-mcp` prepends

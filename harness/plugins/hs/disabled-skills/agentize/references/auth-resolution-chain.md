# Auth Resolution Chain

Shared chain: CLI + MCP-stdio. MCP-HTTP/SSE uses a bearer token at the transport layer; tools may still need this chain.

## Resolution chain (first hit wins)

1. **Explicit flag** — `--api-key <v>`, `--token <v>`. Never logged, never echoed.
2. **Process env vars** — convention: `<TOOL>_<KEY>` (e.g. `ACME_API_KEY`).
3. **dotenv files**, in order:
   - `.env.local` (git-ignored, highest priority)
   - `.env.<NODE_ENV>` (e.g. `.env.production`)
   - `.env`
   Search from CWD, walking up to the package root or repo root.
4. **User config JSON**:
   - Linux/macOS: `$XDG_CONFIG_HOME/<tool>/config.json` or `~/.config/<tool>/config.json`
   - Windows: `%APPDATA%\<tool>\config.json`
5. **Project config JSON**: `./.<tool>rc.json` or `./<tool>.config.json` in CWD.
6. **OS keychain** via `keytar` — written by the `login` command:
   - macOS Keychain, Windows Credential Vault, libsecret on Linux
   - Service name: `<tool>`, account = profile name

Document this chain in `docs/cli.md`. The `doctor` command reports which layer provided each value without revealing the value itself.

## Config file shape

```json
{
  "$schema": "https://<tool>.dev/schema/config.json",
  "profiles": {
    "default": {
      "apiKey": "env:ACME_API_KEY",
      "baseUrl": "https://api.acme.dev",
      "timeoutMs": 30000
    },
    "staging": {
      "apiKey": "keychain:acme/staging",
      "baseUrl": "https://staging.api.acme.dev"
    }
  },
  "activeProfile": "default"
}
```

The resolver supports indirection:
- `env:NAME` — read from process env
- `keychain:<service>/<account>` — read from the OS keychain
- `file:/absolute/path` — read file contents
- plain string — literal value

## `login` and `logout`

```
<tool> login [--profile <name>]
<tool> logout [--profile <name>]
```

`login` prompts interactively, writes to the OS keychain, and updates `activeProfile`. It does not write values to the config file on disk unless the user passes `--save-plaintext` (explicit; discouraged).

## Redaction

- The log redactor masks anything with high entropy, `*key*`, `*token*`, and `Authorization:` headers.
- JSON output of `doctor`:

```json
{
  "apiKey":  { "resolved": true, "source": "keychain:acme/default" },
  "baseUrl": { "resolved": true, "source": "config:~/.config/acme/config.json", "value": "https://api.acme.dev" }
}
```

Sensitive entries: `resolved` + `source`, no `value`. Non-sensitive entries: include `value`.

## Precedence rules

- A value at a higher layer fully overrides a lower layer (no per-field merge).
- Structured config objects merge shallow: later layers replace the keys they define.
- `--profile <name>` selects the active profile before resolution runs; env-only values still win over profile values.

## MCP-HTTP context

Tools receive `ctx.auth` per-request from the transport auth handler:

```ts
const resolved = await resolveAuth({ token: ctx.auth.token, profile: ctx.auth.profile });
```

`resolveAuth` uses the same chain, but layer 1 is the transport-provided token instead of a CLI flag. Layer 6 (keychain) is disabled on non-local deployments.

## Anti-patterns

- Storing an API key as plain JSON by default.
- Logging full request/response bodies.
- `postinstall` scripts that touch the keychain.
- Baking values into Docker images.
- Reading `.env` from parent directories without limit (limit to the package/repo root).

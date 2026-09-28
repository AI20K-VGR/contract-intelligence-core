---
name: hs:agent-browser
injectable: true
description: Automate browsers and apps with agent-browser. Use for testing, screenshots, forms, scraping, Browserbase/cloud browsers, and Electron when real Chrome cookies are not required.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch]
argument-hint: "[url or task]"
metadata:
  compliance-tier: workflow
  upstream: "vercel-labs/agent-browser"
---

# agent-browser Skill

Fast browser automation CLI for AI agents. Chrome/Chromium via CDP with accessibility-tree snapshots and compact `@eN` element refs.

Use `hs:agent-browser` for browser testing, screenshots, form fills, scraping, exploratory QA, cloud browsers, Electron apps, and flows where a fresh/tool-managed browser is fine.

Use `hs:chrome-profile` instead when the task needs the user's actual Chrome profile: existing cookies, logged-in sessions, a specific Google account, a tenant/workspace already open in daily Chrome, or deterministic targeting across multiple Chrome profiles.

## Install / Upgrade

```bash
npm install -g agent-browser     # install (or upgrade) to latest
agent-browser install            # download Chromium (one-time)
agent-browser install --with-deps  # Linux: include system deps
agent-browser upgrade            # self-upgrade the binary
agent-browser --version          # verify
```

Re-run `npm install -g agent-browser` (or `agent-browser upgrade`) periodically — new commands and skills ship with the binary.

## Start here — load live workflow content

This file is a discovery stub, not the usage guide. Before running any `agent-browser` command, load workflow content from the installed CLI so it always matches your version:

```bash
agent-browser skills get core             # workflows, common patterns, troubleshooting
agent-browser skills get core --full      # full command reference + templates
agent-browser skills list                 # see everything available on this version
```

The CLI serves skill content from the installed binary, so instructions never go stale between releases. MUST NOT rely on memorized command lists from this file — always call `agent-browser skills get core` first.

## Specialized skills

Load when the task falls outside browser web pages:

```bash
agent-browser skills get electron          # Electron apps (VS Code, Slack, Discord, Figma, Notion, Spotify)
agent-browser skills get slack             # Slack workspace automation
agent-browser skills get dogfood           # Exploratory testing / QA / bug hunts
agent-browser skills get vercel-sandbox    # agent-browser inside Vercel Sandbox microVMs
agent-browser skills get agentcore         # AWS Bedrock AgentCore cloud browsers
```

## When to use

Default for browser automation that does not depend on the user's real Chrome login state: autonomous sessions, ad-hoc navigation, screenshots, form fills, scraping, multi-tab work, self-verifying build loops, Electron desktop apps, Slack automation, and Browserbase/cloud browsers.

For low-level Chrome DevTools Protocol diagnostics, use the configured `chrome-devtools-mcp` bridge or client when one is available. Reason first: if the task does not need a specific real Chrome profile, Chrome DevTools MCP may use its normal navigation tools. If it does need profile/cookie/account state, use `hs:chrome-profile`; let `chrome-profile open --json` create the tab and bind to its
returned selector before using MCP inspection tools. MUST NOT use raw Chrome DevTools MCP `new_page` or `navigate_page` as the opening path when profile state matters — that breaks profile binding.

Reach for it on triggers like: "test this page", "screenshot the flow", "fill and submit the form", "scrape these results", "drive the Electron app", "automate Slack", "run an exploratory QA pass / bug hunt", "verify the build in a real browser loop", or "run it on a cloud browser (Browserbase/AgentCore/Vercel Sandbox)".

See `references/agent-browser-vs-chrome-devtools.md` for the full routing decision tree (agent-browser vs chrome-profile vs web-testing vs chrome-devtools-mcp).

## Why agent-browser

- Native Rust CLI rather than a Node.js wrapper — fast startup, no Playwright/Puppeteer dependency.
- Drives Chrome/Chromium over the Chrome DevTools Protocol (CDP).
- Accessibility-tree snapshots with stable `@eN` element refs for reliable interaction across page changes.
- Sessions, an authentication vault, state persistence, and video recording built in.
- Works across AI coding agents (Claude Code, Codex, Cursor, Continue, Windsurf).
- Specialized workflows for Electron apps, Slack, exploratory testing, and cloud browsers.

## Cloud browsers

For CI/CD or environments without a local browser:

```bash
export BROWSERBASE_API_KEY="..."
export BROWSERBASE_PROJECT_ID="..."
agent-browser -p browserbase open https://example.com
```

See `references/browserbase-cloud-setup.md` for detailed setup. For AWS Bedrock AgentCore or Vercel Sandbox, run `agent-browser skills get agentcore` / `agent-browser skills get vercel-sandbox`.

## Observability dashboard

Agent Browser exposes an observability dashboard on port 4848, independent of browser sessions. When using a proxied/forwarded URL, stay on the dashboard origin — session tabs, status, and stream traffic proxy internally, so session ports need not be exposed.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Command not found | `npm install -g agent-browser` |
| Chromium missing | `agent-browser install` |
| Linux deps missing | `agent-browser install --with-deps` |
| Stale commands / missing flags | `npm install -g agent-browser` then `agent-browser skills get core --full` |
| Session stale | `agent-browser close` |
| Element not found | Re-run `agent-browser snapshot -i` after page changes |

## Resources

- Upstream: https://github.com/vercel-labs/agent-browser
- Browserbase: https://docs.browserbase.com/

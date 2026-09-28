# Browser Automation Routing

Use `hs:agent-browser` for normal browser automation and testing when a fresh or tool-managed browser is acceptable. Use `hs:chrome-profile` only when the task needs the user's actual Chrome profile state.

## Decision Tree

```
Need browser automation?
|
+-- Needs the user's real Chrome profile, cookies, tenant, or Google account?
|   +-- YES --> hs:chrome-profile
|   +-- NO --> Continue
|
+-- Browser/app testing, screenshots, forms, scraping, exploratory QA?
|   +-- YES --> hs:agent-browser
|   +-- NO --> Continue
|
+-- Repeatable CI/e2e test suite?
|   +-- YES --> hs:web-testing or project-native Playwright/Vitest/Cypress
|   +-- NO --> Continue
|
+-- Low-level Chrome DevTools Protocol inspection?
|   +-- YES --> configured chrome-devtools-mcp bridge/client
|   +-- NO --> Continue
|
+-- Browserbase/cloud browser or Electron workflow?
|   +-- YES --> hs:agent-browser
+-- Otherwise --> hs:web-testing
```

## agent-browser Pattern

```bash
agent-browser --session test1 open https://example.com
agent-browser snapshot -i
agent-browser click @e1
agent-browser close
```

## Chrome Profile Pattern

```bash
chrome-profile doctor
chrome-profile setup
chrome-profile open --json work "https://example.com/dashboard"
```

Then select the page whose URL contains the returned `bind_selector` such as `cdp-open=<token>` through the active MCP bridge, and verify it also contains `cdp-profile=work`.

This restriction applies only after the decision tree says real profile state is required. For generic/profile-independent Chrome diagnostics, Chrome DevTools MCP can use its normal navigation tools. For profile-scoped work, do not use raw Chrome DevTools MCP `new_page` or `navigate_page` as the opening path. Those tools target whichever profile/page the bridge selected.

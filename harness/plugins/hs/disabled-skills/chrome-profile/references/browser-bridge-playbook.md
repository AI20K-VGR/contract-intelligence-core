## Browser Bridge Playbook

The CLI opens tabs in Chrome, but Chrome DevTools MCP must be able to read those tabs. `doctor` summarizes static setup. The live MCP probe above confirms whether the current agent runtime can actually reach the browser.

### Option A: Chrome DevTools MCP auto-connect

Use this when the runtime can expose Chrome DevTools MCP without a fixed remote-debugging endpoint. This avoids depending on a runtime-specific browser extension.

1. Configure Chrome DevTools MCP with auto-connect in the agent runtime's MCP config.
2. Restart the agent session so the MCP server loads.
3. Make a live page-list call. If Chrome prompts for remote-control approval, approve it and retry once.
4. Run:

```bash
chrome-profile doctor
```

Static `doctor` output may still be conservative. The live Chrome DevTools MCP page-list/read probe is the final reachability check.

### Option B: Chrome DevTools MCP attached to daily Chrome

Use this for pure CDP workflows, CI-like local setups, or when auto-connect is not desired. This usually requires relaunching Chrome.

1. Quit Chrome.
2. Relaunch Chrome with remote debugging:

```bash
open -na "Google Chrome" --args \
  --remote-debugging-port=9222 \
  --remote-allow-origins=*
```

3. Add Chrome DevTools MCP to `.claude/.mcp.json`:

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest", "--browserUrl", "http://127.0.0.1:9222"]
    }
  }
}
```

4. Restart the agent session, then run:

```bash
chrome-profile doctor
```

Expected result:

```text
bridge=chrome_devtools_mcp_attached
ok=true
```

If `doctor` reports `chrome_devtools_mcp_auto_connect` or `chrome_devtools_mcp_runtime_probe_required`, the static check found Chrome DevTools MCP config but cannot prove runtime reachability; run the live Chrome DevTools MCP probe. If it reports `cdp_endpoint_without_mcp_config`, Chrome is listening but the MCP config is missing or not loaded. If it reports `none`, run the live probe before
deciding that no readable bridge is available.


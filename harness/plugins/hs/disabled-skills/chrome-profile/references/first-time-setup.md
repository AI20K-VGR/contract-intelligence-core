## First-Time Setup

Install the local CLI shim from the shipped skill directory. Use the path that matches how the skill was installed:

```bash
# Claude Code project-skill layout
bash "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/chrome-profile/scripts/install.sh

# Claude Code plugin layout
bash ~/.claude/plugins/<plugin>/skills/chrome-profile/scripts/install.sh

# Codex native-skill layout, global or project-local
bash ~/.agents/skills/<kit>/chrome-profile/scripts/install.sh
bash .agents/skills/<kit>/chrome-profile/scripts/install.sh
```

If neither path exists, find the installed `chrome-profile/scripts/install.sh` under the project's skill directory and run that script. On Windows, run the sibling `install.cmd`.

Then run the guided checks:

```bash
chrome-profile doctor
chrome-profile setup
chrome-profile list
```

`setup` reads Chrome's `Local State`, proposes stable keys, and writes mappings to:

```text
$XDG_CONFIG_HOME/chrome-profile/profiles.json
```

That per-machine config survives skill and kit updates. Use `chrome-profile setup --yes` for non-interactive bootstrap.


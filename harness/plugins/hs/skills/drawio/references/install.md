# Installation — draw.io prerequisites

The draw.io desktop app is the only runtime dependency for export. All scripts are Python stdlib (plus declared optional deps: defusedxml for validate.py, cairosvg for build_pack.py).

## macOS

```bash
brew install --cask drawio
drawio --version
```

No extra steps after Homebrew install. The binary is `drawio` (no dot).

## Windows

Download from: https://github.com/jgraph/drawio-desktop/releases

```powershell
"C:\Program Files\draw.io\draw.io.exe" --version
```

## Linux

Download `.deb` or `.rpm` from the releases page above. For headless export (no display):

```bash
sudo apt install xvfb          # Debian/Ubuntu
xvfb-run -a drawio --version   # wrap every drawio command
```

Common Linux traps:
- `--no-sandbox` must go at the END of the command (not before the file)
- `export HOME=/tmp` if you get "Home directory not accessible"
- `--disable-gpu` for servers with no GPU
- See `references/troubleshooting.md` for full list.

## WSL2

The CLI lives on the Windows side:
```bash
"/mnt/c/Program Files/draw.io/draw.io.exe" --version
```

Open files with `cmd.exe /c start` + `wslpath -w` to convert paths.

## Skill installation

The skill is part of the harness — no separate install step. It lives at `harness/plugins/hs/skills/drawio/`. All scripts are self-contained (stdlib Python + declared optional deps).

## Graphviz (optional)

Auto-layout for large graphs needs Graphviz:
```bash
brew install graphviz        # macOS
sudo apt install graphviz    # Debian/Ubuntu
```
Without it, coordinates are hand-placed (functional for small diagrams).

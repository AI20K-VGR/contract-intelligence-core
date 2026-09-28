# Mermaid.js v11 -- CLI export (optional)

Export `.mmd` diagrams to SVG/PNG/PDF via `mmdc` CLI (`@mermaid-js/mermaid-cli`). Optional -- primary path stays inline markdown (zero deps).

**Requirement:** Node.js >= 18.

## Installation

```bash
# Global
npm install -g @mermaid-js/mermaid-cli

# Local project
npm install @mermaid-js/mermaid-cli
./node_modules/.bin/mmdc -h

# Without installing, use npx
npx -p @mermaid-js/mermaid-cli mmdc -h
```

## Basic commands

```bash
# SVG (preserves vector quality, recommended for docs)
mmdc -i diagram.mmd -o diagram.svg

# PNG (for slides, email)
mmdc -i diagram.mmd -o diagram.png

# PDF
mmdc -i diagram.mmd -o diagram.pdf

# With theme and background
mmdc -i diagram.mmd -o out.png -t dark -b transparent

# Custom CSS
mmdc -i diagram.mmd -o out.svg --cssFile style.css

# JSON config file
mmdc -i diagram.mmd -o out.svg --configFile mermaid-config.json
```

**Output format** = set by `-o` extension.

## Main flags

| Flag | Description |
|---|---|
| `-i <file>` | Input `.mmd` (use `-` for stdin) |
| `-o <file>` | Output path |
| `-t <theme>` | `default`, `dark`, `forest`, `neutral` |
| `-b <color>` | Background: `transparent`, `white`, `#rrggbb` |
| `--cssFile <file>` | Custom CSS |
| `--configFile <file>` | Mermaid config JSON |

## JSON config file

```json
{
  "theme": "dark",
  "look": "handDrawn",
  "fontFamily": "Arial",
  "flowchart": { "curve": "basis" }
}
```

## Batch processing

```bash
# All .mmd files in a directory
for file in docs/*.mmd; do
  mmdc -i "$file" -o "${file%.mmd}.svg"
done

# find + exec
find docs/ -name "*.mmd" -exec sh -c \
  'mmdc -i "$1" -o "${1%.mmd}.svg"' _ {} \;
```

## Docker (no local Node required)

```bash
docker run --rm \
  -u $(id -u):$(id -g) \
  -v $(pwd):/data \
  ghcr.io/mermaid-js/mermaid-cli/mermaid-cli \
  -i /data/diagram.mmd -o /data/diagram.svg
```

## CI/CD (GitHub Actions)

```yaml
- name: Generate diagrams
  run: |
    npm install -g @mermaid-js/mermaid-cli
    mmdc -i docs/architecture.mmd -o docs/architecture.svg
```

## Stdin piping

```bash
cat << 'EOF' | mmdc --input - -o output.svg
flowchart TD
  A[Start] --> B[End]
EOF
```

## Troubleshooting

| Problem | Solution |
|---|---|
| Permission error (Docker) | Add `-u $(id -u):$(id -g)` |
| Large diagram gets cut off | `NODE_OPTIONS="--max-old-space-size=4096" mmdc ...` |
| Check syntax before rendering | `mmdc -i diagram.mmd -o /dev/null \|\| echo "Invalid"` |

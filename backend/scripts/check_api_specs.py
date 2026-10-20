"""Quick summary of API endpoints."""

from contract_intelligence.main import app

schema = app.openapi()
print(f"API Title: {schema['info']['title']}")
print(f"Version: {schema['info']['version']}")
print()
print("Key AI-related endpoints:")
for path in sorted(schema.get("paths", {})):
    if any(k in path for k in ["/ai/", "healthz", "readyz", "re-ocr", "runs", "upload"]):
        methods = ",".join(schema["paths"][path].keys())
        print(f"  [{methods}] {path}")
print()
total_paths = len(schema.get("paths", {}))
total_ops = sum(len(m) for m in schema["paths"].values())
print(f"Total paths: {total_paths}")
print(f"Total operations: {total_ops}")

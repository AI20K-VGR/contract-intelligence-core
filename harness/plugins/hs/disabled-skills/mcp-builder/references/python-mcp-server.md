# Python MCP Server — Implementation Guide

Use together with `mcp-best-practices.md`. Load in Phase 1 + Phase 2.

Fetch full SDK documentation: `https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md`

---

## Quick reference

```python
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from enum import Enum
import httpx, json

mcp = FastMCP("service_mcp")  # naming: {service}_mcp
CHARACTER_LIMIT = 25000
```

---

## Tool registration pattern

```python
class MyToolInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )
    query: str = Field(..., description="Search string (e.g. 'john', 'team:marketing')",
                       min_length=1, max_length=200)
    limit: Optional[int] = Field(default=20, ge=1, le=100,
                                  description="Max results (default 20)")
    offset: Optional[int] = Field(default=0, ge=0,
                                   description="Pagination offset")

@mcp.tool(
    name="service_search_items",
    annotations={
        "title": "Search Items",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def service_search_items(params: MyToolInput) -> str:
    '''Search items in Service by name or filter.

    Args:
        params (MyToolInput):
            - query (str): Search string
            - limit (Optional[int]): Max results, 1-100 (default 20)
            - offset (Optional[int]): Pagination offset (default 0)

    Returns:
        str: JSON string {total, count, offset, items, has_more, next_offset}
             or "Error: <message>"

    Use when: finding items by keyword.
    Don't use when: you have an ID — use service_get_item instead.
    '''
    try:
        data = await _make_api_request("items/search",
                                        params={"q": params.query,
                                                "limit": params.limit,
                                                "offset": params.offset})
        return _format_paginated(data, params.offset)
    except Exception as e:
        return _handle_api_error(e)
```

---

## Pydantic v2 patterns

```python
from pydantic import BaseModel, Field, field_validator, ConfigDict

class CreateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower()
```

Key Pydantic v2 rules:
- `model_config = ConfigDict(...)` — do not use a nested `Config` class
- `field_validator` + `@classmethod` — do not use `validator` (deprecated)
- `model_dump()` — do not use `dict()`

---

## Shared utilities (extract before implementing tools)

```python
API_BASE_URL = "https://api.service.com/v1"

async def _make_api_request(endpoint: str, method: str = "GET", **kwargs) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method, f"{API_BASE_URL}/{endpoint}", timeout=30.0, **kwargs
        )
        response.raise_for_status()
        return response.json()

def _handle_api_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Error: Resource not found. Check the ID is correct."
        if status == 403:
            return "Error: Permission denied."
        if status == 429:
            return "Error: Rate limit exceeded. Wait before retrying."
        return f"Error: API request failed ({status})"
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Try again."
    return f"Error: {type(e).__name__}: {e}"

def _format_paginated(data: dict, offset: int) -> str:
    items = data.get("items", [])
    total = data.get("total", 0)
    has_more = total > offset + len(items)
    response = {
        "total": total,
        "count": len(items),
        "offset": offset,
        "items": items,
        "has_more": has_more,
        "next_offset": offset + len(items) if has_more else None
    }
    result = json.dumps(response, indent=2)
    if len(result) > CHARACTER_LIMIT:
        half = items[:max(1, len(items) // 2)]
        response["items"] = half
        response["truncated"] = True
        response["truncation_message"] = (
            f"Truncated from {len(items)} to {len(half)} items. "
            "Use 'offset' or add filters."
        )
        result = json.dumps(response, indent=2)
    return result
```

---

## Response format (markdown vs json)

```python
class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"

# In tool:
if params.response_format == ResponseFormat.MARKDOWN:
    lines = [f"# Results for '{params.query}'", ""]
    for item in items:
        lines.append(f"## {item['name']} ({item['id']})")
        lines.append(f"- **Status**: {item['status']}")
    return "\n".join(lines)
else:
    return json.dumps({"items": items, "total": total}, indent=2)
```

---

## Advanced FastMCP

**Context injection** (logging, progress, elicitation):
```python
@mcp.tool()
async def long_op(query: str, ctx: Context) -> str:
    await ctx.report_progress(0.25, "Fetching...")
    await ctx.log_info("Processing", {"query": query})
    results = await fetch(query)
    await ctx.report_progress(1.0, "Done")
    return format_results(results)
```

**Resources** (static/semi-static data):
```python
@mcp.resource("docs://{name}")
async def get_doc(name: str) -> str:
    with open(f"./docs/{name}") as f:
        return f.read()
```

**Lifespan** (persistent connections):
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan():
    db = await connect_db()
    yield {"db": db}
    await db.close()

mcp = FastMCP("service_mcp", lifespan=lifespan)

@mcp.tool()
async def query(sql: str, ctx: Context) -> str:
    db = ctx.request_context.lifespan_state["db"]
    return format(await db.query(sql))
```

**Transport**:
```python
if __name__ == "__main__":
    mcp.run()                                        # stdio (default)
    # mcp.run(transport="streamable_http", port=8000)  # HTTP
    # mcp.run(transport="sse", port=8000)               # SSE
```

---

## Testing (do not run directly)

MCP server blocks stdio when run directly. Use:
- `python -m py_compile server.py` — verify syntax
- `timeout 5s python server.py` — quick smoke test
- Or run in tmux then test from the evaluation harness

---

## Quality checklist

**Design**
- [ ] Tools enable complete workflows (not just endpoint wrappers)
- [ ] Service prefix in all tool names
- [ ] Error messages guide agent toward correct usage

**Implementation**
- [ ] Shared utilities extracted (API client, error handler, formatter)
- [ ] Pydantic v2 for all inputs (Field with description + constraints)
- [ ] Annotations present on all tools
- [ ] CHARACTER_LIMIT check + truncation with guidance
- [ ] Async/await for all I/O
- [ ] Pagination for tools that return lists
- [ ] Docstring complete: summary, args, returns (schema), examples, error handling

**Security**
- [ ] API key from env var, never hardcoded
- [ ] No internal error detail leaked to client

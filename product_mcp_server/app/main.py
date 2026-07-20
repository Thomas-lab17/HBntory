"""Product MCP service foundation.

The HTTP shell is intentionally created first. MCP tools are added in Step 5.
"""

from fastapi import FastAPI

app = FastAPI(title="HBntory Product MCP", version="0.1.0")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "product-mcp"}

"""AI query service entry point."""

from fastapi import FastAPI

app = FastAPI(title="HBntory AI Query Service", version="0.1.0")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-service"}

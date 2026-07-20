"""Backoffice API entry point."""

from fastapi import FastAPI

app = FastAPI(title="HBntory Backoffice API", version="0.1.0")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness endpoint used by local development and orchestration."""
    return {"status": "ok", "service": "backoffice"}

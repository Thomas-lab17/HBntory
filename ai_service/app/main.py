# AI Query Service — independent backend for the Client Web Interface.
# REST (not WebSockets): every question is independent and there is no
# conversation history, so request/response is simpler and stateless.
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import agent

app = FastAPI(title="HBntory AI Query Service", version="0.1.0")

# Allow the public client page (served from another origin) to call us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Query(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    tool_calls: list[str]


@app.get("/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(q: Query) -> QueryResponse:
    """Answer a natural-language question about products and stock."""
    return QueryResponse(**agent.answer(q.question))

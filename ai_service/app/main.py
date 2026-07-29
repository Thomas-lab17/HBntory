"""AI Query Service — HTTP API for the public client."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.agent import Agent
from app.http_data_client import HttpDataClient

logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="HBntory AI Query Service", version="0.2.0")
_agent = Agent(HttpDataClient())


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    intent: str
    question: str


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-service"}


@app.post("/ask", response_model=AskResponse, tags=["chat"])
def ask(body: AskRequest) -> AskResponse:
    result = _agent.repondre(body.question.strip())
    return AskResponse(
        answer=result.reponse,
        intent=result.intent.value,
        question=result.question,
    )

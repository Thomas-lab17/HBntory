"""API HTTP du workflow multi-agents HBntory."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import Cookie, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from app.agent import Agent
from app.domain import ConversationMessage
from app.identity import IdentityResolver, IdentityServiceError

logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="HBntory AI Agent Service", version="1.0.0")
_agent = Agent()
_identity_resolver = IdentityResolver()


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=128)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=12)


class AccessMetadata(BaseModel):
    granted: bool
    scope: str
    authenticated: bool


class AskResponse(BaseModel):
    answer: str
    intent: str
    question: str
    status: str
    request_id: str
    conversation_id: str
    agent: str
    sources: list[str]
    access: AccessMetadata
    used_history: bool


@app.get("/health", tags=["system"])
def health() -> dict[str, str | bool]:
    llm = _agent.workflow.query_agent.llm
    return {
        "status": "ok",
        "service": "ai-service",
        "workflow": "multi-agent",
        "llm_enabled": llm.enabled,
        "llm_model": llm.model,
    }


@app.post("/ask", response_model=AskResponse, tags=["chat"])
def ask(
    body: AskRequest,
    access_token: str | None = Cookie(default=None),
) -> AskResponse:
    try:
        user = _identity_resolver.resolve(access_token)
    except IdentityServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service d'identité HBntory est temporairement indisponible.",
        ) from error
    history = tuple(
        ConversationMessage(role=message.role, content=message.content.strip())
        for message in body.history
    )
    result = _agent.repondre(
        body.question.strip(),
        user_context=user,
        history=history,
    )
    return AskResponse(
        answer=result.reponse,
        intent=result.intent.value,
        question=result.question,
        status=result.status.value,
        request_id=result.request_id,
        conversation_id=body.conversation_id or result.request_id,
        agent=result.agent,
        sources=result.sources,
        access=AccessMetadata(
            granted=result.access_granted,
            scope=result.access_scope,
            authenticated=user.authenticated,
        ),
        used_history=result.used_history,
    )

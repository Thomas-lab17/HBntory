"""Façade de compatibilité autour du workflow multi-agents HBntory."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.domain import (
    ConversationMessage,
    Intent,
    UserContext,
    WorkflowStatus,
)
from app.http_client import HttpDataClient
from app.mcp_client import MCPClient, MockMCPClient
from app.workflow import AgentWorkflow


@dataclass
class AgentAnswer:
    question: str
    intent: Intent
    reponse: str
    status: WorkflowStatus
    request_id: str
    agent: str
    sources: list[str] = field(default_factory=list)
    access_granted: bool = True
    access_scope: str = "public"
    used_history: bool = False
    planner_source: str = "not_run"
    planner_status: str = "not_run"
    planner_confidence: float = 0.0
    planner_failure: str | None = None
    # Conservé pour les anciens consommateurs de la façade.
    tool_result: object | None = None


def build_default_data_client() -> MCPClient:
    mode = os.getenv("AGENT_DATA_CLIENT", "mock").strip().lower()
    if mode == "http":
        return HttpDataClient()
    return MockMCPClient()


def build_default_mcp_client() -> MCPClient:
    """Alias historique conservé pour compatibilité."""
    return build_default_data_client()


class Agent:
    """Point d'entrée stable utilisé par l'API et les tests."""

    def __init__(
        self,
        data_client: MCPClient | None = None,
        *,
        mcp_client: MCPClient | None = None,
    ):
        if data_client is not None and mcp_client is not None:
            raise TypeError("Provide either data_client or mcp_client, not both")
        self.data_client = data_client or mcp_client or build_default_data_client()
        self.workflow = AgentWorkflow(self.data_client)

    def repondre(
        self,
        question: str,
        *,
        user_context: UserContext | None = None,
        history: tuple[ConversationMessage, ...] = (),
    ) -> AgentAnswer:
        result = self.workflow.run(
            question,
            user=user_context,
            history=history,
        )
        return AgentAnswer(
            question=result.question,
            intent=result.intent,
            reponse=result.answer,
            status=result.status,
            request_id=result.request_id,
            agent=result.agent,
            sources=result.sources,
            access_granted=result.access.granted,
            access_scope=result.access.scope,
            used_history=result.used_history,
            planner_source=result.planner_source,
            planner_status=result.planner_status,
            planner_confidence=result.planner_confidence,
            planner_failure=result.planner_failure,
        )

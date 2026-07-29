"""Orchestrateur stateless du workflow multi-agents HBntory."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.agents import (
    AccessAgent,
    BranchAgent,
    EntityResolverAgent,
    GroundingAgent,
    InputGuardAgent,
    ProductAgent,
    QueryAgent,
    ResponseAgent,
    StockAgent,
)
from app.agents.input_guard_agent import InputGuardError
from app.domain import (
    AccessDecision,
    AgentOutput,
    ConversationMessage,
    Intent,
    UserContext,
    WorkflowResult,
    WorkflowState,
    WorkflowStatus,
)

logger = logging.getLogger("hbntory.ai.workflow")


class AgentWorkflow:
    """Planifie, autorise et exécute uniquement les agents nécessaires."""

    def __init__(self, data_client: Any):
        self.input_guard = InputGuardAgent()
        self.query_agent = QueryAgent()
        self.entity_resolver = EntityResolverAgent(data_client)
        self.access_agent = AccessAgent()
        self.product_agent = ProductAgent()
        self.stock_agent = StockAgent(data_client)
        self.branch_agent = BranchAgent()
        self.response_agent = ResponseAgent()
        self.grounding_agent = GroundingAgent()

    def run(
        self,
        question: str,
        *,
        user: UserContext | None = None,
        history: tuple[ConversationMessage, ...] = (),
    ) -> WorkflowResult:
        request_id = uuid.uuid4().hex
        context = user or UserContext.anonymous()
        try:
            normalized_question = self.input_guard.run(question)
        except InputGuardError as error:
            access = AccessDecision(False, str(error), scope=context.role.value)
            return WorkflowResult(
                request_id=request_id,
                question=question,
                intent=Intent.OUT_OF_SCOPE,
                answer=str(error),
                status=WorkflowStatus.ERROR,
                agent="input_guard_agent",
                access=access,
            )

        plan = self.query_agent.run(normalized_question, history)
        state = WorkflowState(
            request_id=request_id,
            question=normalized_question,
            user=context,
            history=history,
            plan=plan,
        )

        if plan.primary_intent is Intent.OUT_OF_SCOPE:
            access = AccessDecision(True, "Aucun outil métier requis.", scope="public")
            return WorkflowResult(
                request_id=request_id,
                question=normalized_question,
                intent=Intent.OUT_OF_SCOPE,
                answer=(
                    "Je peux vous renseigner sur le catalogue fournisseur, les prix, "
                    "la disponibilité, les stocks et les agences HBntory. "
                    "Reformulez votre question dans ce périmètre."
                ),
                status=WorkflowStatus.ANSWERED,
                agent="query_agent",
                access=access,
                used_history=plan.used_history,
            )

        try:
            state.entities = self.entity_resolver.run(state)
            state.access = self.access_agent.evaluate(state)
            if not state.access.granted:
                return WorkflowResult(
                    request_id=request_id,
                    question=normalized_question,
                    intent=plan.primary_intent,
                    answer=state.access.reason,
                    status=WorkflowStatus.DENIED,
                    agent="access_agent",
                    access=state.access,
                    used_history=plan.used_history,
                )

            outputs: list[AgentOutput] = []
            agents_used: list[str] = []

            if plan.has(Intent.ACCESS_INFO, Intent.ACCESS_MANAGEMENT):
                outputs.append(self.access_agent.answer_access(state))
                agents_used.append("access_agent")
            else:
                if plan.has(Intent.PRODUCT_DETAIL, Intent.PRODUCT_SEARCH):
                    outputs.append(self.product_agent.run(state))
                    agents_used.append(self.product_agent.name)
                    if outputs[-1].status is WorkflowStatus.NEEDS_CLARIFICATION:
                        return self._finish(state, outputs, agents_used)

                if plan.has(
                    Intent.STOCK_LOOKUP,
                    Intent.STOCK_BY_PRODUCT,
                    Intent.STOCK_BY_BRANCH,
                ):
                    outputs.append(self.stock_agent.run(state))
                    agents_used.append(self.stock_agent.name)

                if plan.has(Intent.BRANCH_INFO, Intent.BRANCH_LIST):
                    outputs.append(self.branch_agent.run(state))
                    agents_used.append(self.branch_agent.name)

            return self._finish(state, outputs, agents_used)
        except (ConnectionError, PermissionError, TimeoutError, ValueError) as error:
            logger.exception("Workflow %s indisponible: %s", request_id, error)
            access = state.access or AccessDecision(
                True,
                "La demande était autorisée.",
                scope=context.role.value,
            )
            return WorkflowResult(
                request_id=request_id,
                question=normalized_question,
                intent=plan.primary_intent,
                answer=(
                    "Un service de données HBntory est temporairement indisponible. "
                    "Réessayez dans un instant."
                ),
                status=WorkflowStatus.ERROR,
                agent="workflow",
                access=access,
                used_history=plan.used_history,
            )

    def _finish(
        self,
        state: WorkflowState,
        outputs: list[AgentOutput],
        agents_used: list[str],
    ) -> WorkflowResult:
        combined = self.response_agent.run(outputs)
        grounded = self.grounding_agent.run(combined)
        access = state.access or AccessDecision(
            True,
            "Lecture autorisée.",
            scope=state.user.role.value,
        )
        if grounded.status is WorkflowStatus.DENIED and access.granted:
            access = AccessDecision(
                False,
                access.reason,
                effective_branch=access.effective_branch,
                scope=access.scope,
            )
        return WorkflowResult(
            request_id=state.request_id,
            question=state.question,
            intent=state.plan.primary_intent,
            answer=grounded.answer,
            status=grounded.status,
            agent="+".join(agents_used) or self.response_agent.name,
            access=access,
            sources=grounded.sources,
            used_history=state.plan.used_history,
        )

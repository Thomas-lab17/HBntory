"""Assemblage des réponses de plusieurs agents spécialisés."""

from __future__ import annotations

from app.domain import AgentOutput, WorkflowStatus


_STATUS_PRIORITY = {
    WorkflowStatus.ERROR: 4,
    WorkflowStatus.DENIED: 3,
    WorkflowStatus.NEEDS_CLARIFICATION: 2,
    WorkflowStatus.ANSWERED: 1,
}


class ResponseAgent:
    name = "response_agent"

    def run(self, outputs: list[AgentOutput]) -> AgentOutput:
        if not outputs:
            return AgentOutput(
                answer="Je n'ai pas pu construire de réponse fiable.",
                status=WorkflowStatus.ERROR,
            )
        status = max(
            (output.status for output in outputs),
            key=lambda value: _STATUS_PRIORITY[value],
        )
        answer = " ".join(
            output.answer.strip()
            for output in outputs
            if output.answer.strip()
        )
        sources = list(
            dict.fromkeys(
                source
                for output in outputs
                for source in output.sources
            )
        )
        evidence = {
            f"step_{index + 1}": output.evidence
            for index, output in enumerate(outputs)
        }
        return AgentOutput(
            answer=answer,
            status=status,
            sources=sources,
            evidence=evidence,
        )

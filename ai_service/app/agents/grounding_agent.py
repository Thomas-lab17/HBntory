"""Dernier garde-fou : une réponse métier doit être liée à des preuves."""

from __future__ import annotations

from app.domain import AgentOutput, WorkflowStatus


class GroundingAgent:
    name = "grounding_agent"

    _FORBIDDEN_MARKERS = (
        "JWT_SECRET_KEY",
        "INTERNAL_API_KEY",
        "POSTGRES_PASSWORD",
        "access_token=",
    )

    def run(self, output: AgentOutput) -> AgentOutput:
        if any(marker in output.answer for marker in self._FORBIDDEN_MARKERS):
            return AgentOutput(
                answer="Je ne peux pas divulguer de secret ou de jeton système.",
                status=WorkflowStatus.DENIED,
                sources=[],
                evidence={"blocked_sensitive_output": True},
            )
        if output.status is WorkflowStatus.ANSWERED and output.sources and not output.evidence:
            return AgentOutput(
                answer=(
                    "Les données récupérées n'ont pas pu être validées. "
                    "Réessayez dans un instant."
                ),
                status=WorkflowStatus.ERROR,
                sources=output.sources,
                evidence={"grounded": False},
            )
        return output

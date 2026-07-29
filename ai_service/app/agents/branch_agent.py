"""Agent spécialisé dans les agences HBntory."""

from __future__ import annotations

from app.domain import AgentOutput, Intent, WorkflowState, WorkflowStatus


class BranchAgent:
    name = "branch_agent"

    def run(self, state: WorkflowState) -> AgentOutput:
        if state.plan.has(Intent.BRANCH_LIST):
            names = [
                str(branch.get("name"))
                for branch in state.entities.branches
                if branch.get("name")
            ]
            if not names:
                return AgentOutput(
                    answer="Aucune agence HBntory n'est disponible actuellement.",
                    sources=["backoffice:branches"],
                    evidence={"branches": []},
                )
            return AgentOutput(
                answer="Agences HBntory : " + ", ".join(names) + ".",
                sources=["backoffice:branches"],
                evidence={"branches": names},
            )

        branch = state.entities.branch
        if not branch:
            return AgentOutput(
                answer="Précisez le nom de l'agence recherchée.",
                status=WorkflowStatus.NEEDS_CLARIFICATION,
                sources=["backoffice:branches"],
                evidence={"branch": None},
            )
        return AgentOutput(
            answer=(
                f"L'agence {branch} existe dans HBntory. "
                "Son adresse et ses horaires ne sont pas renseignés dans les données actuelles."
            ),
            sources=["backoffice:branches"],
            evidence={"branch": branch},
        )

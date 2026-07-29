"""Politique d'accès déterministe appliquée avant les outils sensibles."""

from __future__ import annotations

from app.domain import (
    AccessDecision,
    AgentOutput,
    Intent,
    UserContext,
    UserRole,
    WorkflowState,
    WorkflowStatus,
)


class AccessAgent:
    """Décide du périmètre; il ne fait aucune confiance au prompt utilisateur."""

    def evaluate(self, state: WorkflowState) -> AccessDecision:
        plan = state.plan
        user = state.user
        requested_branch = state.entities.branch or plan.branch

        if plan.has(Intent.ACCESS_INFO):
            if not user.authenticated:
                return AccessDecision(
                    False,
                    "Authentification requise pour consulter vos accès.",
                    scope="anonymous",
                )
            return AccessDecision(True, "Identité vérifiée.", scope=user.role.value)

        if plan.has(Intent.ACCESS_MANAGEMENT):
            if user.role is not UserRole.ADMIN:
                return AccessDecision(
                    False,
                    "La gestion des accès est réservée aux administrateurs.",
                    scope=user.role.value,
                )
            return AccessDecision(
                True,
                "Administrateur vérifié; les mutations restent désactivées dans le chat.",
                scope="admin_read_only",
            )

        if plan.has(Intent.STOCK_BY_BRANCH):
            if user.role is UserRole.ANONYMOUS:
                return AccessDecision(
                    False,
                    (
                        "La vue complète du stock d'une agence nécessite une "
                        "connexion au backoffice."
                    ),
                    scope="public_item_only",
                )
            if user.role is UserRole.COMMON:
                if not user.branch_name:
                    return AccessDecision(
                        False,
                        "Votre compte n'est associé à aucune agence.",
                        scope="common",
                    )
                if (
                    requested_branch
                    and requested_branch.casefold() != user.branch_name.casefold()
                ):
                    return AccessDecision(
                        False,
                        (
                            "Votre compte peut consulter uniquement le stock de "
                            f"l'agence {user.branch_name}."
                        ),
                        effective_branch=user.branch_name,
                        scope="stock:read:self",
                    )
                return AccessDecision(
                    True,
                    "Accès limité à l'agence de l'utilisateur.",
                    effective_branch=user.branch_name,
                    scope="stock:read:self",
                )
            return AccessDecision(
                True,
                "Accès administrateur aux stocks des agences.",
                effective_branch=requested_branch,
                scope="stock:read:any",
            )

        # Le catalogue, les agences et la disponibilité d'un article précis
        # constituent le périmètre public du chatbot HBntory.
        return AccessDecision(
            True,
            "Lecture publique HBntory.",
            effective_branch=requested_branch,
            scope="public",
        )

    def answer_access(self, state: WorkflowState) -> AgentOutput:
        user = state.user
        if state.plan.has(Intent.ACCESS_MANAGEMENT):
            return AgentOutput(
                answer=(
                    "Votre identité administrateur est vérifiée, mais le chatbot "
                    "HBntory reste volontairement en lecture seule. Pour affecter "
                    "ou réaffecter un utilisateur à une agence, utilisez l'écran "
                    "Utilisateurs du backoffice ; aucune modification n'a été effectuée."
                ),
                status=WorkflowStatus.DENIED,
                sources=["backoffice:identity"],
                evidence={"role": user.role.value, "mutation_executed": False},
            )

        branch = f", agence {user.branch_name}" if user.branch_name else ""
        return AgentOutput(
            answer=(
                f"Vous êtes connecté en tant que {user.username or 'utilisateur'} "
                f"avec le rôle {user.role.value}{branch}."
            ),
            sources=["backoffice:identity"],
            evidence={
                "user_id": user.user_id,
                "role": user.role.value,
                "branch_name": user.branch_name,
            },
        )

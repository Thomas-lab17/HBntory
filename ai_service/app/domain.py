"""Objets de domaine partagés par le workflow d'agents HBntory."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Intent(str, Enum):
    PRODUCT_DETAIL = "produit"
    PRODUCT_SEARCH = "recherche_produit"
    STOCK_LOOKUP = "stock"
    STOCK_BY_PRODUCT = "stock_par_produit"
    STOCK_BY_BRANCH = "stock_par_agence"
    BRANCH_INFO = "agence"
    BRANCH_LIST = "liste_agences"
    ACCESS_INFO = "acces"
    ACCESS_MANAGEMENT = "gestion_acces"
    OUT_OF_SCOPE = "hors_scope"


class WorkflowStatus(str, Enum):
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    DENIED = "denied"
    ERROR = "error"


class UserRole(str, Enum):
    ANONYMOUS = "anonymous"
    COMMON = "common"
    ADMIN = "admin"


@dataclass(frozen=True)
class UserContext:
    """Identité vérifiée côté serveur, jamais déclarée dans le JSON client."""

    role: UserRole = UserRole.ANONYMOUS
    user_id: int | None = None
    username: str | None = None
    branch_id: int | None = None
    branch_name: str | None = None

    @property
    def authenticated(self) -> bool:
        return self.role is not UserRole.ANONYMOUS and self.user_id is not None

    @classmethod
    def anonymous(cls) -> "UserContext":
        return cls()


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str


@dataclass
class QueryPlan:
    intents: tuple[Intent, ...]
    confidence: float
    product_query: str | None = None
    branch: str | None = None
    stock_filter: str | None = None
    used_history: bool = False
    list_all_products: bool = False

    @property
    def primary_intent(self) -> Intent:
        return self.intents[0] if self.intents else Intent.OUT_OF_SCOPE

    def has(self, *intents: Intent) -> bool:
        return any(intent in self.intents for intent in intents)


@dataclass
class ResolvedEntities:
    product: dict[str, Any] | None = None
    product_candidates: list[dict[str, Any]] = field(default_factory=list)
    branch: str | None = None
    branches: list[dict[str, Any]] = field(default_factory=list)
    product_total: int = 0


@dataclass(frozen=True)
class AccessDecision:
    granted: bool
    reason: str
    effective_branch: str | None = None
    scope: str = "public"


@dataclass
class AgentOutput:
    answer: str
    status: WorkflowStatus = WorkflowStatus.ANSWERED
    sources: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    request_id: str
    question: str
    intent: Intent
    answer: str
    status: WorkflowStatus
    agent: str
    access: AccessDecision
    sources: list[str] = field(default_factory=list)
    used_history: bool = False


@dataclass
class WorkflowState:
    request_id: str
    question: str
    user: UserContext
    history: tuple[ConversationMessage, ...]
    plan: QueryPlan
    entities: ResolvedEntities = field(default_factory=ResolvedEntities)
    access: AccessDecision | None = None

"""Tests du planificateur LLM-first et de ses gardes déterministes."""

from __future__ import annotations

import unittest

from app.agents.query_agent import QueryAgent
from app.domain import Intent
from app.ollama_client import OllamaInterpretation


class FakeLlm:
    def __init__(
        self,
        payload: dict | None = None,
        failure_code: str | None = None,
        *,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self.payload = payload
        self.failure_code = failure_code
        self.calls: list[tuple[str, list[str]]] = []

    def interpret_detailed(
        self,
        question: str,
        history: list[str],
    ) -> OllamaInterpretation:
        self.calls.append((question, history))
        return OllamaInterpretation(
            payload=self.payload,
            failure_code=self.failure_code,
        )


def valid_plan(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "intents": ["stock_lookup"],
        "product_query": "écran 27 pouces",
        "branch": "Lyon",
        "stock_filter": None,
        "list_all_products": False,
        "used_history": False,
        "confidence": 0.92,
    }
    payload.update(overrides)
    return payload


class QueryAgentTests(unittest.TestCase):
    def test_ollama_is_called_first_and_valid_plan_is_accepted(self) -> None:
        llm = FakeLlm(valid_plan())
        agent = QueryAgent(llm=llm)

        plan = agent.run("Y a-t-il un écran 27 pouces à Lyon ?")

        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(plan.primary_intent, Intent.STOCK_LOOKUP)
        self.assertEqual(plan.planner_source, "ollama")
        self.assertEqual(plan.planner_status, "success")
        self.assertIsNone(plan.planner_failure)

    def test_tool_query_uses_user_words_not_llm_invention(self) -> None:
        llm = FakeLlm(valid_plan(product_query="serveur quantique inventé"))
        agent = QueryAgent(llm=llm)
        question = "Y a-t-il un écran 27 pouces à Lyon ?"

        plan = agent.run(question)

        self.assertEqual(plan.product_query, question)

    def test_unavailable_ollama_exposes_deterministic_fallback(self) -> None:
        llm = FakeLlm(failure_code="llm_unavailable")
        agent = QueryAgent(llm=llm)

        plan = agent.run("Quel est le prix du produit 101 ?")

        self.assertEqual(plan.primary_intent, Intent.PRODUCT_DETAIL)
        self.assertEqual(plan.planner_source, "deterministic_fallback")
        self.assertEqual(plan.planner_status, "fallback")
        self.assertEqual(plan.planner_failure, "llm_unavailable")

    def test_low_confidence_plan_falls_back(self) -> None:
        llm = FakeLlm(valid_plan(confidence=0.2))
        agent = QueryAgent(llm=llm, min_llm_confidence=0.65)

        plan = agent.run("Y a-t-il un écran 27 pouces à Lyon ?")

        self.assertEqual(plan.planner_source, "deterministic_fallback")
        self.assertEqual(plan.planner_failure, "llm_low_confidence")

    def test_invalid_intent_falls_back(self) -> None:
        llm = FakeLlm(valid_plan(intents=["delete_stock"]))
        agent = QueryAgent(llm=llm)

        plan = agent.run("Y a-t-il un écran 27 pouces à Lyon ?")

        self.assertEqual(plan.planner_source, "deterministic_fallback")
        self.assertEqual(plan.planner_failure, "llm_invalid_intents")

    def test_ungrounded_branch_is_rejected(self) -> None:
        llm = FakeLlm(valid_plan(branch="Paris"))
        agent = QueryAgent(llm=llm)

        plan = agent.run("Y a-t-il un écran 27 pouces à Lyon ?")

        self.assertEqual(plan.planner_source, "deterministic_fallback")
        self.assertEqual(plan.planner_failure, "llm_ungrounded_branch")

    def test_access_mutation_misclassification_is_overridden(self) -> None:
        llm = FakeLlm(
            valid_plan(
                intents=["access_info"],
                product_query=None,
                branch=None,
            )
        )
        agent = QueryAgent(llm=llm)

        plan = agent.run("Donne accès à Alice à l'agence de Lyon.")

        self.assertEqual(plan.primary_intent, Intent.ACCESS_MANAGEMENT)
        self.assertEqual(plan.planner_source, "deterministic_fallback")
        self.assertEqual(plan.planner_failure, "llm_security_override")

    def test_aggregate_stock_misclassification_is_overridden(self) -> None:
        llm = FakeLlm(
            valid_plan(
                intents=["stock_lookup"],
                product_query=None,
            )
        )
        agent = QueryAgent(llm=llm)

        plan = agent.run("Donne-moi tout le stock de l'agence de Lyon.")

        self.assertEqual(plan.primary_intent, Intent.STOCK_BY_BRANCH)
        self.assertEqual(plan.planner_source, "deterministic_fallback")
        self.assertEqual(plan.planner_failure, "llm_security_override")

    def test_in_scope_question_rejected_by_llm_uses_safe_fallback(self) -> None:
        llm = FakeLlm(
            valid_plan(
                intents=["out_of_scope"],
                product_query=None,
                branch=None,
            )
        )
        agent = QueryAgent(llm=llm)

        plan = agent.run("Quel est le prix du produit 101 ?")

        self.assertEqual(plan.primary_intent, Intent.PRODUCT_DETAIL)
        self.assertEqual(plan.planner_failure, "llm_scope_conflict")


if __name__ == "__main__":
    unittest.main()

"""Validation déterministe de l'entrée avant tout appel d'outil ou de modèle."""

from __future__ import annotations


class InputGuardError(ValueError):
    """Question inutilisable par le workflow."""


class InputGuardAgent:
    def __init__(self, max_length: int = 2000):
        self.max_length = max_length

    def run(self, question: str) -> str:
        normalized = " ".join((question or "").split())
        if not normalized:
            raise InputGuardError("La question ne peut pas être vide.")
        if len(normalized) > self.max_length:
            raise InputGuardError(
                f"La question ne peut pas dépasser {self.max_length} caractères."
            )
        return normalized

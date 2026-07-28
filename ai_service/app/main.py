"""
Démonstration de la Couche 3 — Agent IA.
Lancer avec : python -m agent_ia.main
"""

import logging

from agent_ia import Agent

logging.basicConfig(level=logging.INFO, format="%(message)s")


QUESTIONS_TEST = [
    "Quel est le prix de la chaise ergonomique ?",
    "Est-ce que la chaise ergonomique est disponible à Lyon ?",
    "Est-ce que la chaise ergonomique est disponible à Paris ?",
    "Est-ce que le bureau assis-debout est disponible à Paris ?",
    "Quels sont les horaires de l'agence de Lyon ?",
    "Quelle est la capitale de la France ?",  # hors scope
]


def main() -> None:
    agent = Agent()

    for question in QUESTIONS_TEST:
        print("\n" + "=" * 70)
        print(f"Question : {question}")
        reponse = agent.repondre(question)
        print(f"Intention : {reponse.intent.value}")
        print(f"Réponse   : {reponse.reponse}")


if __name__ == "__main__":
    main()

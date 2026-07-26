"""
Client MCP (interface + implémentation de démonstration)
==========================================================
Ce module définit l'interface attendue pour un client MCP, ainsi
qu'une implémentation "mock" avec des données factices, utile pour
développer et tester la Couche 3 sans dépendre d'un serveur MCP réel.

Pour brancher un vrai serveur MCP, il suffit d'implémenter une classe
respectant la même interface (méthodes get_produit / get_stock /
get_branche) et de l'injecter dans ToolCaller.
"""

from __future__ import annotations

from typing import Optional, Protocol


class MCPClient(Protocol):
    """Interface attendue par le ToolCaller."""

    def get_produit(self, nom_ou_ref: str) -> Optional[dict]:
        ...

    def get_stock(self, nom_ou_ref: str, branche: Optional[str] = None) -> Optional[dict]:
        ...

    def get_branche(self, nom_ou_ref: str) -> Optional[dict]:
        ...


class MockMCPClient:
    """
    Implémentation factice, à remplacer en production par un vrai
    client MCP (ex : appel HTTP/stdio vers un serveur MCP réel).
    """

    _PRODUITS = {
        "chaise ergonomique": {
            "reference": "CH-ERG-001",
            "nom": "Chaise ergonomique",
            "prix": 189.90,
            "description": "Chaise de bureau ergonomique avec support lombaire réglable.",
        },
        "bureau assis-debout": {
            "reference": "BUR-AD-002",
            "nom": "Bureau assis-debout",
            "prix": 349.00,
            "description": "Bureau électrique réglable en hauteur, 100-130 cm.",
        },
    }

    _STOCKS = {
        ("chaise ergonomique", "Lyon"): {"quantite": 12},
        ("chaise ergonomique", "Paris"): {"quantite": 0},
        ("bureau assis-debout", "Lyon"): {"quantite": 4},
        # Pas d'entrée pour "bureau assis-debout" à Paris -> donnée manquante
    }

    _BRANCHES = {
        "lyon": {
            "nom": "Agence Lyon Part-Dieu",
            "adresse": "12 rue de la République, 69003 Lyon",
            "horaires": "Lun-Sam 9h-19h",
        },
        "paris": {
            "nom": "Agence Paris Bastille",
            "adresse": "8 boulevard Voltaire, 75011 Paris",
            "horaires": "Lun-Sam 9h30-19h30",
        },
    }

    def get_produit(self, nom_ou_ref: str) -> Optional[dict]:
        key = nom_ou_ref.strip().lower()
        return self._PRODUITS.get(key)

    def get_stock(self, nom_ou_ref: str, branche: Optional[str] = None) -> Optional[dict]:
        key = (nom_ou_ref.strip().lower(), (branche or "").strip())
        return self._STOCKS.get(key)

    def get_branche(self, nom_ou_ref: str) -> Optional[dict]:
        key = nom_ou_ref.strip().lower()
        return self._BRANCHES.get(key)

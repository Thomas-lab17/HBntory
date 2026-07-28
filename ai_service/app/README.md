# Couche 3 — Agent IA

Implémentation Python des trois sous-composants demandés.

## Structure

```
agent_ia/
├── __init__.py          # exports du package
├── intent_router.py     # (1) Intent router
├── tool_caller.py        # (2) Tool caller (avec logs structurés)
├── response_builder.py   # (3) Response builder (aucune invention)
├── mcp_client.py         # interface MCP + client mock pour tester
├── agent.py              # orchestrateur reliant les 3 sous-composants
└── main.py                # démo exécutable
```

## Les trois sous-composants

### 1. Intent router (`intent_router.py`)
Classifie la question en `PRODUIT`, `STOCK`, `BRANCHE` ou `HORS_SCOPE`
via un classifieur par mots-clés (facilement remplaçable par un appel
LLM en injectant `classify_fn` dans `IntentRouter`).
Si `HORS_SCOPE`, l'agent (`agent.py`) répond immédiatement **sans**
appeler `ToolCaller`.

### 2. Tool caller (`tool_caller.py`)
Appelle les outils MCP nécessaires dans l'ordre logique pour
l'intention détectée (ex : pour `STOCK`, on récupère d'abord le
produit, puis le stock). Chaque appel est loggé avec :
outil, paramètres, statut (`ok` / `vide` / `erreur`), durée en ms.

### 3. Response builder (`response_builder.py`)
Transforme les données réellement récupérées en réponse en français
naturel. **Aucune invention** : si une donnée manque (produit
introuvable, stock non renseigné, etc.), le message le dit
explicitement plutôt que de deviner.

## Utilisation

```python
from agent_ia import Agent

agent = Agent()  # utilise MockMCPClient par défaut (données de démo)
resultat = agent.repondre("Est-ce que la chaise ergonomique est disponible à Lyon ?")

print(resultat.intent)   # Intent.STOCK
print(resultat.reponse)  # "« Chaise ergonomique » est disponible à Lyon : 12 unité(s) en stock."
```

Pour brancher un vrai serveur MCP, implémentez une classe avec les
méthodes `get_produit`, `get_stock`, `get_branche` (voir le
`Protocol MCPClient` dans `mcp_client.py`) et injectez-la :

```python
agent = Agent(mcp_client=MonVraiClientMCP())
```

## Lancer la démo

```bash
python -m agent_ia.main
```

## Points d'extension suggérés

- Remplacer le classifieur par règles de `IntentRouter` par un appel LLM
  (structuré en JSON) pour une classification plus robuste.
- Remplacer `_extraire_entites` (naïf) dans `agent.py` par une vraie
  extraction d'entités (NER ou LLM structuré).
- Adapter le format des logs de `tool_caller.py` (ex : JSON) selon
  votre stack d'observabilité.

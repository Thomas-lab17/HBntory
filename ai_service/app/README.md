# HBntory AI Agent Service

Le service IA utilise un workflow modulaire, stateless et fondé sur les
données réelles :

```text
InputGuardAgent
  -> QueryAgent (Ollama en premier, repli déterministe)
  -> AccessAgent (garde déterministe avant les données)
  -> EntityResolverAgent (catalogue + agences)
  -> AccessAgent (confirmation avec les entités résolues)
  -> ProductAgent / StockAgent / BranchAgent
  -> ResponseAgent
  -> GroundingAgent
```

## Principes

- Le catalogue vient exclusivement du Product MCP et contient toutes les pages
  de l'API fournisseur.
- Les quantités viennent exclusivement de l'API interne du backoffice.
- Le rôle et l'agence ne sont jamais acceptés dans le JSON du navigateur.
  Ils sont résolus depuis le cookie JWT HttpOnly via `/auth/me`.
- Une demande refusée ou hors périmètre n'appelle aucun outil de stock.
- Le chatbot reste en lecture seule. Une demande de gestion d'accès ne modifie
  jamais un utilisateur et renvoie vers l'écran Utilisateurs du backoffice.
- Une recherche produit ambiguë demande une précision.
- L'historique fourni par le client permet les questions comme
  « Et à Paris ? » sans mémoire globale entre utilisateurs.

## Politique d'accès

| Profil | Catalogue | Stock d'un produit précis | Stock complet d'une agence | Gestion d'accès |
|---|---:|---:|---:|---:|
| Anonyme | oui | oui | non | non |
| Common | oui | oui | son agence | non |
| Admin | oui | oui | toutes les agences | lecture seule dans le chat |

## API

`POST /ask`

```json
{
  "question": "Y a-t-il un écran 27 pouces dans l'agence de Lyon ?",
  "conversation_id": "optional-id",
  "history": [
    {"role": "user", "content": "Le produit 3 est-il disponible à Lyon ?"},
    {"role": "assistant", "content": "Oui, 40 unités sont disponibles."}
  ]
}
```

La réponse conserve les champs historiques `answer`, `intent` et `question`,
et ajoute `status`, `request_id`, `agent`, `sources`, `access`, `planning` et
`used_history`.

`planning` indique si Ollama a produit le plan ou si le repli déterministe a
été utilisé :

```json
{
  "source": "deterministic_fallback",
  "status": "fallback",
  "confidence": 0.9,
  "failure_code": "llm_unavailable"
}
```

## Ollama local

Quand il est activé, Ollama reçoit chaque question validée et la traduit en
plan JSON structuré. Il ne répond jamais directement à l'utilisateur, ne
décide pas des autorisations et n'accède à aucun tool. Le plan est ensuite
contraint par un schéma JSON minimal, puis validé par du code déterministe.
Les prix, catégories et devises sont relus directement dans la question. Le
contrôle d'accès déterministe précède toute résolution de données et est
confirmé avant le tool métier.

```env
AI_LLM_ENABLED=true
OLLAMA_API_BASE=http://host.docker.internal:11434
MODEL_NAME=gemma3:1b
OLLAMA_TIMEOUT_SECONDS=15
AI_LLM_MIN_CONFIDENCE=0.65
```

Ollama est installé et lancé sur la machine hôte. Le conteneur AI le rejoint
via `host.docker.internal`; aucun serveur Ollama, modèle ou volume Ollama
n'est créé par Docker. Télécharge le modèle une seule fois sur l'hôte :

```bash
ollama pull gemma3:1b
ollama serve
```

Si le serveur hôte n'écoute pas sur l'interface accessible à Docker, lance-le
avec `OLLAMA_HOST=0.0.0.0:11434 ollama serve`. Le modèle d'environ 815 Mo offre
un meilleur compromis que la variante 270M pour comprendre les formulations
françaises. Il suffit de remplacer `MODEL_NAME` dans `.env` et de télécharger
le même modèle sur l'hôte.

Le client accepte jusqu'à 15 secondes pour une interprétation. La
conservation en mémoire (`OLLAMA_KEEP_ALIVE`) et la taille de contexte sont
des réglages du serveur Ollama hôte, pas de Docker.

En cas d'indisponibilité ou de réponse JSON invalide d'Ollama, le workflow
continue automatiquement avec le routeur déterministe. La cause est exposée
par `planning.failure_code` sans publier le détail technique de l'exception.
Les codes actuels couvrent notamment `llm_disabled`, `llm_unavailable`,
`llm_model_unavailable`, `llm_invalid_response`, `llm_low_confidence`,
`llm_invalid_intents`, `llm_ungrounded_branch`,
`llm_history_branch_conflict`, `llm_scope_conflict`,
`llm_semantic_override` et `llm_security_override`.

La documentation de référence est
[`docs/ai_agent_architecture.md`](../../docs/ai_agent_architecture.md).

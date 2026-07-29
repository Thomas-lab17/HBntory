# HBntory AI Agent Service

Le service IA utilise un workflow modulaire, stateless et fondé sur les
données réelles :

```text
InputGuardAgent
  -> QueryAgent (règles rapides, Ollama optionnel si ambigu)
  -> EntityResolverAgent (catalogue + agences)
  -> AccessAgent
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
et ajoute `status`, `request_id`, `agent`, `sources`, `access` et
`used_history`.

## Ollama local

Les questions courantes sont traitées sans modèle pour réduire la latence.
Ollama est sollicité uniquement lorsque le routeur déterministe manque de
confiance. Il traduit alors la question en plan JSON structuré ; il ne répond
jamais directement à l'utilisateur et n'accède ni au stock ni aux permissions.

```env
AI_LLM_ENABLED=true
OLLAMA_API_BASE=http://host.docker.internal:11434
MODEL_NAME=gemma3:1b
OLLAMA_TIMEOUT_SECONDS=120
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

Le client accepte jusqu'à 120 secondes pour une interprétation sur CPU. La
conservation en mémoire (`OLLAMA_KEEP_ALIVE`) et la taille de contexte sont
des réglages du serveur Ollama hôte, pas de Docker.

En cas d'indisponibilité ou de réponse JSON invalide d'Ollama, le workflow
continue automatiquement avec le routeur déterministe.

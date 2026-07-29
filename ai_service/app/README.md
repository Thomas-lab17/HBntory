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

## Ollama optionnel

Les questions courantes sont traitées sans modèle pour réduire la latence.
Ollama est sollicité uniquement lorsque le routeur déterministe manque de
confiance.

```env
AI_LLM_ENABLED=true
OLLAMA_API_BASE=http://host.docker.internal:11434
MODEL_NAME=gemma3:1b
```

Sans Ollama, le workflow continue automatiquement avec le routeur
déterministe.

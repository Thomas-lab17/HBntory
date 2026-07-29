# HBntory — Synthèse d'architecture et stratégie IA

Dernière mise à jour : 29 juillet 2026  
Branche de travail : `feat/ai-agent`

## 1. Résumé exécutif

HBntory sépare volontairement trois types de données :

1. le **catalogue fournisseur**, qui contient tous les produits disponibles
   dans l'API Product ;
2. le **stock local**, qui contient uniquement la quantité d'un produit dans
   une agence ;
3. l'**identité utilisateur**, qui détermine les données de stock que la
   personne peut consulter.

Supprimer une ligne de stock ne supprime donc jamais le produit du catalogue.
Le produit reste disponible à la commande tant qu'il est fourni par l'API
Product.

Le chatbot utilise désormais une architecture hybride :

- des règles déterministes pour les cas métier connus, les autorisations et
  les appels aux données ;
- Ollama avec `gemma3:1b` pour interpréter les formulations ambiguës ;
- des réponses construites uniquement à partir des données réelles renvoyées
  par le Product MCP et le backoffice.

Le modèle ne reçoit pas le droit de modifier les stocks, les utilisateurs ou
les accès.

## 2. Architecture générale

```mermaid
flowchart LR
    User["Utilisateur"] --> Web["Client Web<br/>localhost:8080"]
    Web --> AI["AI Service<br/>localhost:8001"]

    AI --> Ollama["Ollama sur l'hôte<br/>gemma3:1b<br/>localhost:11434"]
    AI --> Auth["Backoffice /auth/me<br/>identité et permissions"]
    AI --> StockAPI["API interne Backoffice<br/>stocks et agences"]
    AI --> MCP["Product MCP<br/>localhost:8002"]

    Auth --> Backoffice["Backoffice<br/>localhost:8000"]
    StockAPI --> Backoffice
    Backoffice --> DB[("PostgreSQL")]

    MCP --> Supplier["API Product fournisseur<br/>localhost:5001"]
```

### Responsabilité de chaque service

| Service | Responsabilité | Source de vérité |
|---|---|---|
| API Product fournisseur | Tous les produits disponibles à l'opérateur | Catalogue produit |
| Product MCP | Lecture, pagination et normalisation du catalogue | API Product |
| Backoffice | Utilisateurs, agences et quantités locales | PostgreSQL |
| AI Service | Compréhension, contrôle d'accès et orchestration | Aucune donnée métier persistée |
| Ollama | Interprétation sémantique d'une question ambiguë | Aucun accès direct aux données |
| Client Web | Conversation et transmission de l'historique | Mémoire locale de l'interface |

## 3. Catalogue et stock : règle fonctionnelle centrale

Le catalogue et le stock ont des cycles de vie différents.

```mermaid
flowchart TD
    Supplier["Produit présent chez le fournisseur"] --> Catalog["Visible dans le catalogue"]
    Catalog --> Add["Peut être ajouté ou commandé dans une agence"]
    Add --> Stock["Ligne de stock locale"]
    Stock --> Zero["Quantité ramenée à zéro"]
    Zero --> Delete["Ligne retirée du stock"]
    Delete --> Catalog
```

- Le catalogue est relu depuis l'API fournisseur.
- La pagination est parcourue jusqu'à obtenir toutes les pages annoncées par
  l'API.
- PostgreSQL conserve seulement l'identifiant externe et la quantité par
  agence, sans recopier la fiche produit.
- Une suppression dans « Mon stock » supprime uniquement la relation locale
  agence/produit.
- Le catalogue permet ensuite de retrouver et recommander ce même produit.

Les listes de stock sont triées par quantité croissante, puis par nom de
produit dans l'ordre alphabétique lorsque les quantités sont identiques.

## 4. Workflow IA modulaire

```mermaid
flowchart TD
    Question["Question + historique"] --> Guard["InputGuardAgent"]
    Guard --> Query["QueryAgent"]
    Query -->|"formulation connue"| Rules["Plan déterministe"]
    Query -->|"confiance < 0,7"| LLM["Ollama / gemma3:1b"]
    LLM --> Plan["Plan JSON structuré"]
    Rules --> Resolve["EntityResolverAgent"]
    Plan --> Resolve
    Resolve --> Access["AccessAgent"]
    Access -->|"refusé"| Denied["Réponse de refus"]
    Access -->|"autorisé"| Specialized["ProductAgent / StockAgent / BranchAgent"]
    Specialized --> Response["ResponseAgent"]
    Response --> Grounding["GroundingAgent"]
    Grounding --> Answer["Réponse finale + sources"]
```

### Ce qui « raisonne »

Sans Ollama, `QueryAgent` applique des règles :

- normalisation des accents et de la ponctuation ;
- détection de mots-clés comme `stock`, `disponible`, `prix`, `agence` ;
- reconnaissance d'alias comme `écran` → `monitor` et
  `pouces` → `inch` ;
- rapprochement des mots avec les noms, descriptions, catégories, SKU et
  tags du catalogue ;
- récupération du produit précédent pour une question telle que
  « Et à Paris ? ».

Avec Ollama activé, une question jugée ambiguë est envoyée à `gemma3:1b`. Le
modèle doit seulement retourner :

```json
{
  "intents": ["stock_lookup"],
  "product_query": "écran 27 pouces",
  "branch": "Lyon",
  "confidence": 0.91
}
```

Ollama ne produit pas directement la réponse finale. Il ne peut pas appeler
les outils métier, modifier la base de données ou décider seul d'un accès.

### Pourquoi une architecture hybride

| Besoin | Réponse architecturale |
|---|---|
| Comprendre plusieurs formulations naturelles | Ollama interprète les cas ambigus |
| Répondre rapidement aux questions courantes | Routeur déterministe en premier |
| Ne pas inventer une quantité ou un prix | Réponse fondée sur les API réelles |
| Protéger les stocks des autres agences | Politique d'accès déterministe |
| Continuer si Ollama est indisponible | Repli automatique sur les règles |
| Faciliter les tests | Agents stateless et clients de données injectables |

## 5. Agents et responsabilités

| Agent | Rôle |
|---|---|
| `InputGuardAgent` | Valide et normalise la question |
| `QueryAgent` | Produit les intentions métier |
| `EntityResolverAgent` | Identifie produit et agence dans les données réelles |
| `AccessAgent` | Applique les droits selon l'identité authentifiée |
| `ProductAgent` | Répond sur le catalogue, le prix et la fiche produit |
| `StockAgent` | Répond sur une quantité, un produit ou une agence |
| `BranchAgent` | Répond sur les agences |
| `ResponseAgent` | Assemble les résultats des agents spécialisés |
| `GroundingAgent` | Refuse une réponse métier sans preuve ou source |

Le workflow est **stateless** : aucune identité ou conversation globale n'est
partagée entre utilisateurs. L'historique utile est envoyé explicitement avec
chaque requête.

## 6. Authentification et stratégie d'accès

L'AI Service ne fait jamais confiance à un rôle ou à une agence envoyés dans
le JSON du navigateur.

1. Le navigateur transmet automatiquement le cookie JWT `HttpOnly`.
2. L'AI Service appelle `/auth/me`.
3. Le backoffice retourne l'utilisateur, son rôle et son agence actuels.
4. `AccessAgent` applique la politique métier.

| Profil | Catalogue | Stock d'un produit précis | Stock complet d'une agence | Gestion d'accès par chat |
|---|---:|---:|---:|---:|
| Anonyme | Oui | Oui | Non | Non |
| Common | Oui | Oui | Son agence uniquement | Non |
| Admin | Oui | Oui | Toutes les agences | Lecture seule |

Une demande telle que « donne accès à Alice » ne modifie rien. Même pour un
administrateur, le chatbot renvoie vers l'écran Utilisateurs du backoffice.

## 7. Configuration Ollama sur la machine hôte

Ollama n'est pas exécuté dans Docker. Le conteneur `ai-service` se connecte au
serveur Ollama installé sur l'ordinateur via `host.docker.internal`.

Variables actives :

```env
AI_LLM_ENABLED=true
OLLAMA_API_BASE=http://host.docker.internal:11434
MODEL_NAME=gemma3:1b
OLLAMA_TIMEOUT_SECONDS=120
```

Sur l'hôte, installe et démarre le modèle :

```bash
ollama pull gemma3:1b
ollama serve
```

Si nécessaire, utilise `OLLAMA_HOST=0.0.0.0:11434 ollama serve` pour rendre le
port joignable depuis Docker Desktop. Docker ne télécharge ni ne conserve le
modèle.

Le modèle `gemma3:1b` représente environ 815 Mo. Il a été choisi comme
compromis entre :

- une empreinte suffisamment faible pour un poste de développement ;
- une meilleure compréhension du français que la variante 270M ;
- la capacité à produire le petit objet JSON attendu par `QueryAgent`.

Le timeout d'interprétation est fixé à 120 secondes pour accepter l'inférence
CPU de la machine hôte. Les réglages de conservation en mémoire et de contexte
restent ceux du serveur Ollama local. Si Ollama ne répond pas dans le délai ou
renvoie un JSON invalide, le service continue avec le plan déterministe.

## 8. API de conversation

Requête :

```http
POST /ask
Content-Type: application/json
```

```json
{
  "question": "Y a-t-il un écran 27 pouces dans l'agence de Lyon ?",
  "conversation_id": "conversation-123",
  "history": [
    {
      "role": "user",
      "content": "Je cherche un écran 27 pouces."
    }
  ]
}
```

La réponse expose notamment :

- `answer` : réponse utilisateur ;
- `intent` : intention principale ;
- `status` : répondu, refusé, erreur ou clarification ;
- `agent` : agents métier réellement utilisés ;
- `sources` : systèmes ayant fourni les preuves ;
- `access` : portée d'accès effective ;
- `used_history` : indication de réutilisation du contexte.

L'endpoint `/health` indique également si le LLM est activé et le nom du
modèle configuré.

## 9. Travaux réalisés pendant la session

### Backoffice et catalogue

- Le catalogue a été défini comme l'ensemble complet des produits fournis par
  l'API Product.
- La récupération multi-pages a été sécurisée dans le backoffice et le
  Product MCP.
- La suppression d'un produit du stock ne le supprime plus du catalogue.
- La liste de stock est triée par quantité croissante puis par nom.
- La navigation de la vue stock ne présente plus de sous-lignage
  indésirable.

### Product MCP

- Parcours des pages avec `limit`, `offset` et `count`.
- Compatibilité avec plusieurs formes historiques de réponse.
- Détection des pages répétées et des catalogues incomplets.
- Limite de sécurité empêchant une boucle de pagination infinie.

### Service IA

- Remplacement de l'agent monolithique par un workflow modulaire.
- Ajout de la résolution d'entités produit/agence.
- Ajout de la politique d'accès par profil.
- Ajout des questions de suivi avec historique.
- Ajout de réponses fondées sur les sources réelles.
- Ajout d'Ollama comme interpréteur optionnel et maintenant activé.
- Conservation d'une façade compatible avec l'ancien service.

### Client Web

- Transmission d'un identifiant de conversation.
- Envoi des derniers messages utiles au service IA.
- Prise en charge de questions de suivi comme « Et le prix ? » ou
  « Et à Paris ? ».

### Intégration et Git

- La branche `feat/ai-agent` est basée sur `main` au commit `90026ff`.
- Le workflow multi-agents est enregistré dans le commit `a8aff0e`.
- Les apports des branches collaboratrices concernant le MCP, le service IA
  et le backoffice sont présents dans l'historique de `main`.

## 10. Vérifications

Les vérifications automatisées couvrent :

- les intentions et les enchaînements d'agents ;
- la disponibilité d'un écran 27 pouces à Lyon ;
- les recherches ambiguës ;
- les questions catalogue, prix et stock ;
- la réutilisation de l'historique ;
- les refus d'accès par profil ;
- l'identité issue du cookie ;
- les pannes des services de données ;
- la pagination complète du catalogue MCP.

Commandes :

```bash
PYTHONPATH=ai_service python3 -m unittest discover -s ai_service/tests -q
python3 -m unittest discover -s product_mcp_server/tests -q
docker compose config --quiet
```

Test de bout en bout recommandé :

```bash
docker compose up -d --build
curl http://localhost:8001/health
curl http://localhost:11434/api/tags
```

Puis ouvrir `http://localhost:8080` et poser :

> Y a-t-il un écran 27 pouces dans l'agence de Lyon ?

## 11. Limites et évolutions possibles

1. `gemma3:1b` reste un petit modèle : certaines formulations complexes
   pourront nécessiter une clarification.
2. Le LLM sert uniquement de planificateur de requête. La formulation finale
   reste déterministe pour garantir la fidélité aux données.
3. La politique utilisateur ne gère actuellement qu'une agence principale
   par utilisateur.
4. Le chat reste volontairement en lecture seule.
5. Une évolution utile serait d'exposer dans les métadonnées si le plan
   déterministe ou Ollama a été retenu, afin de faciliter l'observabilité.

## 12. Critères de réussite

La chaîne est considérée opérationnelle lorsque :

- le serveur Ollama de l'hôte répond à `/api/tags` et contient `gemma3:1b` ;
- `/health` annonce `llm_enabled: true` et `llm_model: gemma3:1b` ;
- le catalogue renvoie toutes les pages du fournisseur ;
- une question produit/stock renvoie des sources réelles ;
- un utilisateur `common` ne peut pas lire le stock complet d'une autre
  agence ;
- la suppression d'une ligne de stock laisse le produit visible dans le
  catalogue.

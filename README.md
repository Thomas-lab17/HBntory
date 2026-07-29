# HBntory — Plan technique et objectifs

HBntory est un MVP de gestion de stock par agence, complété par une interface
publique capable de répondre à des questions sur les produits et leur
disponibilité. Le projet sépare les responsabilités pour garder les données de
stock, les données produit externes et l'assistant IA indépendants.

## Stack technique choisie

| Besoin | Technologie |
|---|---|
| Backend Backoffice | Python + FastAPI |
| Base de données | PostgreSQL |
| Modèles de données | SQLAlchemy |
| Validation des requêtes | Pydantic |
| Authentification | JWT dans cookie sécurisé HttpOnly |
| Hashage des mots de passe | Argon2 ou bcrypt |
| Interface Backoffice | HTML, CSS, JavaScript |
| Interface Client public | HTML, CSS, JavaScript |
| Communication frontend/backend | API REST avec JSON |
| API Product externe | Requêtes HTTP REST |
| Serveur MCP | Python + SDK/framework MCP |
| Service IA | Python + FastAPI |
| Tests | Pytest |
| Variables sensibles | Fichier `.env` non versionné |

## Architecture retenue

```text
client-web (nginx, :8080) ──> ai-service (:8001)
                                  ├──> backoffice (:8000) ──> PostgreSQL
                                  └──> product-mcp (:8002) ──> API Product externe
```

### Rôles et services

Il ne faut pas confondre les rôles humains et les services techniques :

- `admin` est un utilisateur Backoffice qui gère les comptes ;
- `common` est un utilisateur Backoffice qui gère le stock de son agence ;
- le client public ne se connecte pas et interroge uniquement le service IA ;
- Product MCP est un service technique qui consulte l'API Product externe. Il
  n'est pas un utilisateur et n'accède pas directement à PostgreSQL.

Pour le MVP, seul le Backoffice accède à PostgreSQL. Le service IA lira les
stocks à travers une API REST interne en lecture seule.

## Objectif de chaque partie

| Partie | Objectif | Responsabilités prévues |
|---|---|---|
| `backoffice/` | Sécuriser l'administration et la gestion de stock. | API FastAPI, interface Backoffice HTML/CSS/JS, authentification JWT, rôles, utilisateurs, agences et règles de stock. |
| `ai_service/` | Répondre aux questions publiques avec des données fiables. | API de questions, lecture du stock, appels aux outils produit MCP et intégration du fournisseur LLM. |
| `product_mcp_server/` | Isoler l'accès aux données produit externes. | Outils MCP `list_products` et `get_product_details`, gestion des erreurs de réseau et d'indisponibilité. |
| `client_web/` | Donner au visiteur une interface simple. | Champ de question, appel au service IA, affichage du chargement, de la réponse et des erreurs. |
| `docs/` | Centraliser les consignes de développement et d'exploitation. | Guide Docker, commandes de lancement, diagnostic et documentation fonctionnelle. |
| `docker-compose.yml` | Lancer le MVP complet localement. | Réseau entre services, variables d'environnement et ports locaux. |

## Démarrer l'environnement de développement

Prérequis : Docker et Docker Compose.

```bash
cp .env.example .env
# Choisir un mot de passe PostgreSQL dans .env
docker compose up --build
```

Services disponibles une fois les conteneurs démarrés :

- Client public : `http://localhost:8080`
- API Backoffice : `http://localhost:8000/docs`
- Service IA : `http://localhost:8001/docs`
- Service Product MCP : `http://localhost:8002/docs`

Pour arrêter l'environnement, utiliser `docker compose down`. Les données de
PostgreSQL sont conservées dans le volume Docker `postgres_data`; utiliser
`docker compose down -v` seulement si elles doivent être supprimées.

Le guide complet des fichiers Docker, des commandes, des logs et de Docker
Desktop est disponible dans
[docs/docker_implementation.md](docs/docker_implementation.md).

La synthèse des rôles, des flux et des choix techniques est disponible dans
[docs/architecture_synthesis.md](docs/architecture_synthesis.md).

La synthèse détaillée du workflow multi-agents, de la stratégie hybride avec
Ollama et des travaux d'intégration est disponible dans
[docs/ai_agent_architecture_and_session_summary.md](docs/ai_agent_architecture_and_session_summary.md).



## Décisions principales

### Backend Python avec FastAPI

Nous utilisons Python et FastAPI pour le Backoffice et le service IA.

Avantage : FastAPI permet de créer rapidement des endpoints REST, de valider les données et de documenter automatiquement les APIs.

Limite : il faut organiser clairement les routes, services et permissions pour éviter un backend désordonné.

### PostgreSQL et SQLAlchemy

Nous utilisons PostgreSQL pour les données locales et SQLAlchemy pour les modèles.

Données enregistrées localement :
- utilisateurs ;
- agences ;
- stock par agence ;
- identifiant externe des produits ;
- rôles ;
- mots de passe hachés ;
- statut des utilisateurs supprimés.

Les détails produit ne sont pas stockés localement. Ils viennent toujours de l’API Product.

### JWT pour l’authentification

Nous utilisons des JWT pour identifier l’utilisateur connecté.

Le JWT contient au minimum :
- l’identifiant utilisateur ;
- son rôle ;
- son agence, si c’est un utilisateur commun ;
- une date d’expiration.

Le JWT doit être placé dans un cookie `HttpOnly`, `Secure` en production et
`SameSite` configuré. Cela évite que JavaScript puisse lire directement le token.

Avantage : le frontend et le backend communiquent facilement avec une API REST.

Limite : il faut gérer l’expiration et, si nécessaire, l’invalidation des tokens. À chaque requête sensible, le backend vérifiera aussi que l’utilisateur existe encore et qu’il n’est pas supprimé.

### Interface HTML, CSS et JavaScript

Les deux interfaces seront simples et sans framework frontend complexe.

- Le Backoffice permet la connexion, la gestion de stock et la gestion des utilisateurs.
- Le Client public permet de poser une question à l’IA.

Avantage : développement plus rapide et moins de complexité.

Limite : l’interface sera moins riche qu’une application React, mais cela est suffisant pour le MVP.

---

# Roadmap MVP — alignée avec Trello

La source de vérité du planning est le tableau
[HBntory — Plan MVP](https://trello.com/b/pgnSWet2/hbntory-plan-mvp). Les
cartes prioritaires P0 sont regroupées en six jalons : un jalon est terminé
uniquement lorsque sa preuve ou ses tests sont disponibles.

| Jalon | Objectif | Cartes Trello P0 |
|---|---|---|
| 1 — Cadrage | Valider le périmètre avant le développement fonctionnel. | 00 Agenda et pilotage ; 01 Architecture et diagramme ; 02 Décisions REST/MCP et MVP. |
| 2 — Fondations | Rendre les données et règles de stock opérationnelles. | 03 Schéma PostgreSQL et modèles SQLAlchemy ; 04 Création des tables et données initiales. |
| 3 — Backoffice | Sécuriser les usages internes et permettre la gestion de stock. | 05 JWT et mots de passe ; 06 Autorisations ; 07 Product API ; 08 Opérations de stock ; 09 Gestion des utilisateurs ; 10 Interface Backoffice. |
| 4 — IA | Fonder les réponses sur les produits et stocks réels. | 11 Product MCP Server ; 12 API de stock en lecture seule ; 13 AI Query Service ; 14 Endpoint REST IA. |
| 5 — Client | Donner accès aux questions IA depuis une page publique. | 15 Interface Client public. |
| 6 — Livraison | Vérifier le flux de bout en bout et préparer la démonstration. | 16 Tests Backoffice ; 17 Tests MCP et IA ; 18 Intégration et démonstration ; 19 README et présentation ; 20 Vérification des consignes. |

## Détail des étapes du MVP

### Jalon 1 — Cadrage

- Décrire les responsabilités du Backoffice, de PostgreSQL, du MCP, du service
  IA et du client, ainsi que les flux entre eux.
- Utiliser REST pour les interfaces et MCP pour les données produit.
- Documenter le MVP, les éléments reportés et les options.

Critère de sortie : l'architecture, le diagramme et les décisions techniques
sont validés.

### Jalon 2 — Fondations

- Créer les modèles `Branch`, `User` et `Stock`, leurs relations et la
  contrainte agence/produit.
- Ne stocker localement que `external_product_id`, jamais les détails produit.
- Ajouter timestamps et suppression logique des utilisateurs.
- Créer automatiquement les tables et ajouter les données initiales : un
  administrateur haché, deux agences et un stock de démonstration.

Critère de sortie : la base se crée au démarrage et protège les règles de stock.

### Jalon 3 — Backoffice

- Authentifier avec des mots de passe Argon2 ou bcrypt, un login/logout et un
  JWT expirant dans un cookie HttpOnly.
- Refuser les utilisateurs supprimés et appliquer les rôles côté backend :
  l'admin gère exclusivement les utilisateurs ; le rôle `common` gère
  exclusivement le stock de sa propre agence.
- Ajouter l'API Product au Backoffice pour vérifier les identifiants et gérer
  produit inconnu ou erreur API.
- Permettre de lister, ajouter et retirer du stock sans quantité négative.
- Permettre à l'admin de créer, lister, modifier et supprimer logiquement les
  utilisateurs communs.
- Créer les pages de connexion, de stock et d'administration avec Fetch API.

Critère de sortie : les droits sont appliqués par l'API et les parcours
Backoffice sont utilisables.

### Jalon 4 — IA

- Exposer les outils MCP `list_products` et
  `get_product_details(product_id)` avec des erreurs explicites.
- Fournir une API interne de lecture seule pour le stock d'un produit, le stock
  dans une agence, les produits d'une agence et une liste de courses.
- Connecter l'agent IA à ces deux sources, journaliser les appels d'outils et
  valider la requête REST de question.
- Prendre en charge : détail produit, agences disponibles, produits d'une
  agence et vérification d'une liste de courses ; refuser clairement ce qui est
  hors périmètre ou indisponible.

Critère de sortie : toute réponse IA repose sur Product MCP et les stocks réels.

### Jalon 5 — Client public

- Proposer un champ de question et un bouton d'envoi sans authentification.
- Montrer le chargement, la réponse IA ou une erreur compréhensible.
- Fournir des exemples de questions correspondant aux quatre cas du MVP.

Critère de sortie : un visiteur peut interroger le système depuis le navigateur.

Exemples de questions à proposer dans le client :

- « Quels sont les détails du produit `123` ? »
- « Dans quelles agences le produit `123` est-il disponible ? »
- « Quels produits sont disponibles dans l'agence Paris ? »
- « Puis-je acheter 2 unités du produit `123` et 1 unité du produit `456` ? »

### Jalon 6 — Livraison

- Tester les opérations de stock, les rôles, la suppression logique et le refus
  d'accès à une autre agence.
- Tester produit connu/inconnu, erreur Product API, disponibilité, liste de
  courses et informations manquantes.
- Vérifier le flux complet : connexion, stock, administration, question client
  et réponse IA fondée sur MCP et le stock réel.
- Finaliser le README, les slides et la démonstration à trois.

Critère de sortie : toutes les exigences P0 sont démontrables et testées.

## Hors MVP

Les éléments P2 ne sont réalisés qu'après la validation complète des cartes
P0 : historique de stock, export CSV, tests end-to-end et déploiement. Docker
Compose est déjà fourni ici comme aide au développement local, sans étendre le
périmètre fonctionnel du MVP.

---

# Répartition conseillée à trois

| Personne | Responsabilité |
|---|---|
| Personne 1 | Base PostgreSQL, SQLAlchemy, JWT, rôles, API Backoffice. |
| Personne 2 | Product API, MCP Server, API stock interne, AI Query Service. |
| Personne 3 | Pages HTML/CSS/JS Backoffice et Client, tests interface, README, présentation. |

Tous participent à l’intégration finale et aux tests.

---

# MVP à terminer avant tout

- Authentification JWT sécurisée.
- Utilisateurs, agences et stock dans PostgreSQL.
- Ajout/retrait de stock avec règles de sécurité.
- Gestion des utilisateurs par l’admin.
- API Product connectée.
- MCP avec liste et détail produit.
- Service IA avec les quatre types de questions imposés.
- Interface Client simple.
- README et démonstration.

Les améliorations visuelles, tableaux de bord, historique de stock, streaming IA et déploiement sont optionnels.

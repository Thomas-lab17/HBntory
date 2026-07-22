# Synthèse de l'architecture HBntory

## Décision principale

Les rôles de l'application sont `admin` et `common`.

`client` et `MCP` ne sont pas des rôles PostgreSQL :

| Acteur | Authentification | Accès PostgreSQL | Responsabilité |
|---|---|---|---|
| Admin | JWT Backoffice | Via l'API Backoffice | Gérer les utilisateurs. |
| Common | JWT Backoffice | Via l'API Backoffice | Gérer le stock de son agence. |
| Client public | Aucune | Aucun | Poser une question au service IA. |
| Service IA | Interne | Aucun accès direct | Lire le stock par l'API Backoffice. |
| Product MCP | Interne | Aucun | Lire les produits dans Product API. |

Cette séparation correspond au README et évite de donner la base à tous les
services.

## Flux retenus

```text
Backoffice HTML/JS -> API Backoffice -> PostgreSQL
Client public      -> Service IA     -> API Backoffice (stock)
                                    -> Product MCP -> Product API
```

## Base de données mise en place

Trois tables sont définies dans `backoffice/app/models.py` :

- `branches` : agences ;
- `users` : comptes Backoffice, rôles et suppression logique ;
- `stocks` : quantité par agence et `external_product_id`.

Contraintes importantes :

```text
UNIQUE(branch_id, external_product_id)
CHECK(quantity >= 0)
```

Les détails produit ne sont jamais stockés dans PostgreSQL.

En développement, le démarrage crée une seule fois :

- les agences Paris et Lyon ;
- l'administrateur `admin` ;
- l'utilisateur `personne1` rattaché à Paris ;
- 10 unités du produit externe `123` à Paris.

Les données de démonstration ne sont pas créées quand `APP_ENV=production`.

## Authentification mise en place

Le Backoffice utilise :

- Argon2id pour les mots de passe ;
- un JWT expirant ;
- un cookie `HttpOnly` et `SameSite=Lax` ;
- `Secure` lorsque `APP_ENV=production` ;
- une nouvelle lecture de l'utilisateur en base pour chaque requête protégée ;
- le refus du compte si `deleted_at` est renseigné.

Routes disponibles :

```text
POST /auth/login
GET  /auth/me
POST /auth/logout
```

## Client Backoffice mis en place

FastAPI sert directement les fichiers dans `backoffice/static/` :

- `/` affiche le formulaire de connexion ;
- `/app.html` vérifie la session et affiche le rôle ;
- le bouton de déconnexion appelle `/auth/logout`.

Le client public sur le port `8080` reste séparé et sans authentification,
comme demandé par le README.

## Avantages et inconvénients

### Un seul accès PostgreSQL par le Backoffice

Avantages : architecture simple, règles centralisées, MCP indépendant du
stock. Inconvénient : le service IA dépend de la disponibilité de l'API
Backoffice pour lire le stock.

### JWT dans un cookie

Avantages : le navigateur gère la session et JavaScript ne peut pas lire le
token grâce à `HttpOnly`. Inconvénients : le logout supprime le cookie mais ne
révoque pas une copie déjà volée du JWT ; `SameSite=Lax` réduit le risque CSRF
sans le supprimer pour tous les scénarios futurs.

### Création des tables avec `create_all`

Avantage : très simple pour le MVP étudiant. Inconvénient : les modifications
futures du schéma demanderont des migrations ou la recréation de la base de
développement.

### Données de démonstration automatiques

Avantage : connexion et démonstration immédiates. Inconvénient : les mots de
passe par défaut sont uniquement adaptés au développement ; ils doivent être
fournis par l'environnement et changés pour un déploiement réel.

### Interface servie par FastAPI

Avantage : un seul conteneur et aucune configuration CORS pour le Backoffice.
Inconvénient : cette solution est moins adaptée qu'un serveur statique dédié
pour une interface volumineuse, ce qui n'est pas le cas du MVP.

## Ce qui reste à faire

- autorisations backend admin/common sur les routes métier ;
- opérations d'ajout et retrait de stock ;
- gestion des utilisateurs par l'admin ;
- API interne de stock en lecture seule pour le service IA ;
- outils Product MCP et intégration du service IA ;
- interface publique de questions.

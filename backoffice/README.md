# HBntory Backoffice

Le backoffice permet de gérer le stock par branche et les utilisateurs. Il est composé d'une API Flask et d'une interface web statique en JavaScript.

## Démarrer l'application

Depuis la racine du projet :

```bash
docker compose up --build
```

Puis ouvrir [http://localhost:5000](http://localhost:5000).

Pour arrêter le conteneur :

```bash
docker compose down
```

### Comptes de démonstration

| Utilisateur | Mot de passe | Rôle | Accès |
|---|---|---|---|
| `admin` | `admin` | `admin` | Gestion des utilisateurs |
| `personne1` | `common` | `common` | Stock de la branche Paris |

Ces identifiants sont uniquement destinés à la démonstration.

## Fonctionnement général

```text
Navigateur
    |
    | HTML, CSS, JavaScript
    v
Flask : interface web + API JSON
    |
    v
Données en mémoire dans backend/data.py
```

- `frontend/index.html` définit les écrans et les formulaires.
- `frontend/style.css` contient le style de l'interface.
- `frontend/app.js` envoie les requêtes à l'API et affiche la vue correspondant au rôle.
- `backend/app.py` contient les routes, l'authentification et les règles d'accès.
- `backend/data.py` contient les branches, les utilisateurs et le stock de démonstration.

Cette version ne possède pas encore de base de données : les données sont gardées en mémoire et sont réinitialisées au redémarrage de l'application.

## Rôles et permissions

### Administrateur

L'administrateur peut :

- consulter la liste des utilisateurs ;
- créer des utilisateurs ;
- modifier leur nom, mot de passe ou branche ;
- supprimer un utilisateur.

L'administrateur ne peut pas gérer le stock et son propre compte ne peut pas être modifié ou supprimé.

### Utilisateur `common`

Un utilisateur `common` est lié à une seule branche. Il peut :

- consulter le stock de sa branche ;
- ajouter des unités à un produit ;
- retirer des unités de son stock.

La branche est déterminée côté serveur à partir de l'utilisateur connecté. Le client ne peut donc pas demander le stock d'une autre branche en envoyant un autre identifiant.

## Authentification JWT

La connexion se fait avec `POST /api/login`. L'API renvoie un token JWT valable 12 heures. L'interface le conserve dans `localStorage` sous `hbntory_token` et l'envoie ensuite dans l'en-tête :

```text
Authorization: Bearer <token>
```

Pour chaque requête protégée, le serveur :

1. vérifie la signature et l'expiration du token ;
2. retrouve l'utilisateur correspondant ;
3. vérifie que le compte n'est pas supprimé ;
4. vérifie le rôle et la branche nécessaires à la route.

Les mots de passe sont hachés avec `scrypt` grâce à Werkzeug. Le mot de passe n'est jamais renvoyé dans une réponse JSON.

## API

L'URL de base est `http://localhost:5000`.

### Liste des endpoints

| Méthode | Endpoint | Accès | Fonction |
|---|---|---|---|
| `GET` | `/` | Public | Sert l'interface web |
| `POST` | `/api/login` | Public | Connecte un utilisateur et renvoie un JWT |
| `GET` | `/api/me` | Public | Vérifie le token et retourne l'utilisateur courant |
| `GET` | `/api/branches` | Utilisateur connecté | Liste les branches disponibles |
| `GET` | `/api/stock` | `common` | Consulte le stock de sa branche |
| `POST` | `/api/stock/add` | `common` | Ajoute du stock dans sa branche |
| `POST` | `/api/stock/remove` | `common` | Retire du stock de sa branche |
| `GET` | `/api/users` | `admin` | Liste les utilisateurs |
| `POST` | `/api/users` | `admin` | Crée un utilisateur `common` |
| `PATCH` | `/api/users/<user_id>` | `admin` | Modifie un utilisateur |
| `DELETE` | `/api/users/<user_id>` | `admin` | Supprime doucement un utilisateur |

Les endpoints qui nécessitent une connexion attendent le token dans l'en-tête
`Authorization: Bearer <token>`.

### Authentification

#### `POST /api/login`

Route publique. Connecte un utilisateur.

Corps JSON :

```json
{
  "username": "personne1",
  "password": "common"
}
```

Réponse : `200 OK` avec `token`, `token_type` et `user`.

Erreurs : `400` si un champ manque, `401` si les identifiants sont invalides.

#### `GET /api/me`

Route publique. Vérifie le token présent et retourne l'utilisateur courant. Retourne `{"user": null}` si aucun token valide n'est fourni.

### Branches

#### `GET /api/branches`

Accessible à tout utilisateur connecté. Retourne les branches disponibles, utilisées par les formulaires administrateur.

### Stock, réservé au rôle `common`

Toutes les opérations de stock utilisent automatiquement la branche de l'utilisateur connecté.

#### `GET /api/stock`

Retourne le stock de la branche de l'utilisateur.

Exemple de réponse :

```json
{
  "branch": "Paris",
  "stock": [
    {"id": 1, "product_id": 101, "quantity": 10}
  ]
}
```

#### `POST /api/stock/add`

Ajoute des unités. Si le produit existe déjà dans la branche, sa quantité est augmentée au lieu de créer une seconde ligne.

Corps JSON :

```json
{
  "product_id": 101,
  "quantity": 5
}
```

Réponse : `201 Created`. Les deux valeurs doivent être des entiers positifs.

#### `POST /api/stock/remove`

Retire des unités. Le stock ne peut pas devenir négatif.

Corps JSON :

```json
{
  "product_id": 101,
  "quantity": 3
}
```

Réponse : `200 OK`.

- `400` si la quantité est invalide ou supérieure au stock disponible ;
- `404` si le produit n'existe pas dans la branche.

### Utilisateurs, réservé au rôle `admin`

#### `GET /api/users`

Retourne tous les utilisateurs, y compris ceux marqués comme supprimés.

#### `POST /api/users`

Crée un utilisateur. Le serveur force toujours le rôle `common`.

Corps JSON :

```json
{
  "username": "alice",
  "password": "secret",
  "branch_id": 2
}
```

Réponse : `201 Created`.

- `400` si les champs sont invalides ou la branche inconnue ;
- `409` si le nom existe déjà.

#### `PATCH /api/users/<user_id>`

Modifie un utilisateur `common`. Les champs acceptés sont `username`, `password` et `branch_id`.

Exemple :

```json
{
  "branch_id": 2,
  "password": "nouveau-secret"
}
```

Le mot de passe peut être omis pour le conserver. Le compte administrateur est protégé.

#### `DELETE /api/users/<user_id>`

Effectue une suppression douce : `is_deleted` passe à `true`, mais l'utilisateur reste dans la liste interne.

Un compte supprimé ne peut plus se connecter et ses tokens existants sont refusés lors des requêtes suivantes.

## Codes HTTP principaux

| Code | Signification |
|---|---|
| `200` | Requête réussie |
| `201` | Ressource créée ou stock ajoutée |
| `400` | Données invalides ou règle métier non respectée |
| `401` | Token absent ou invalide, ou identifiants incorrects |
| `403` | Rôle non autorisé pour cette route |
| `404` | Utilisateur ou produit introuvable |
| `409` | Nom d'utilisateur déjà utilisé |

## Tester l'API avec curl

Connexion :

```bash
curl -X POST http://localhost:5000/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"personne1","password":"common"}'
```

Après avoir copié le token reçu :

```bash
curl http://localhost:5000/api/stock \
  -H 'Authorization: Bearer <token>'
```

Pour les routes administrateur, se connecter avec `admin` et utiliser son token.

# Documentation du module JWT

Le fichier [app/auth.py](../backoffice/app/auth.py) contient toute la
fonctionnalité d'authentification. Il peut être copié dans une application
FastAPI existante.

## Installation

Ajouter les dépendances :

```text
fastapi
argon2-cffi
PyJWT
```

## Fonctions disponibles

### `hash_password(password)`

Transforme un mot de passe en hash Argon2.

```python
user.password_hash = hash_password("mon-mot-de-passe")
```

Le mot de passe original ne doit jamais être enregistré en base.

### `verify_password(password, password_hash)`

Compare un mot de passe reçu avec le hash enregistré.

```python
if verify_password(password, user.password_hash):
    print("Mot de passe correct")
```

La fonction retourne `True` ou `False`.

### `create_auth_router(find_by_username, find_by_id, ...)`

Construit les routes d'authentification. Cette fonction ne connaît pas la base
de données : elle reçoit deux fonctions fournies par l'application.

```python
router = create_auth_router(find_by_username, find_by_id)
app.include_router(router)
```

Paramètres :

| Paramètre | Rôle |
|---|---|
| `find_by_username` | Retourne un utilisateur à partir de son nom. |
| `find_by_id` | Retourne un utilisateur à partir de son identifiant. |
| `secret` | Secret de signature du JWT. Par défaut, lit `JWT_SECRET_KEY`. |
| `expire_minutes` | Durée de validité du JWT. 30 minutes par défaut. |
| `cookie_secure` | Force ou non l'attribut `Secure` du cookie. |

## Objet utilisateur attendu

Les fonctions `find_by_username` et `find_by_id` doivent retourner un objet
contenant au minimum :

```python
user.id
user.username
user.password_hash
user.role
```

Champs optionnels :

```python
user.branch_id   # agence d'un utilisateur common
user.deleted     # booléen
user.deleted_at  # date de suppression logique
```

Le rôle `common` désigne un utilisateur normal. Le rôle `admin` désigne un
administrateur.

## Routes créées

### `POST /auth/login`

Reçoit :

```json
{
  "username": "personne1",
  "password": "secret"
}
```

Actions effectuées :

1. normalisation du nom d'utilisateur ;
2. recherche de l'utilisateur ;
3. vérification du hash Argon2 ;
4. refus si l'utilisateur est supprimé ;
5. création du JWT ;
6. ajout du JWT dans le cookie `access_token`.

Le cookie possède :

```text
HttpOnly
SameSite=Lax
Secure en production
```

### `GET /auth/me`

Lit le cookie `access_token`, vérifie la signature et l'expiration du JWT, puis
recherche l'utilisateur avec `find_by_id`.

La route retourne `401 Unauthorized` si :

- le cookie est absent ;
- le JWT est invalide ou expiré ;
- l'utilisateur n'existe plus ;
- l'utilisateur est supprimé.

### `POST /auth/logout`

Supprime le cookie `access_token` du navigateur. La réponse est `204 No
Content`.

## Contenu du JWT

Le token contient :

```json
{
  "sub": "1",
  "role": "common",
  "branch_id": 1,
  "iat": "date de création",
  "exp": "date d'expiration"
}
```

Le mot de passe n'est jamais placé dans le JWT.

## Exemple avec une base existante

```python
from app.auth import create_auth_router
from app.models import User


def find_by_username(username: str):
    return db.query(User).filter(User.username == username).first()


def find_by_id(user_id: int):
    return db.get(User, user_id)


app.include_router(
    create_auth_router(find_by_username, find_by_id)
)
```

La base de données reste donc indépendante du module JWT.

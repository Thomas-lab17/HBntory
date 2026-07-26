# Backoffice API

Objectif : fournir l'API sécurisée utilisée par le backoffice pour gérer les
utilisateurs, les agences et le stock.

Cette partie contient le module JWT réutilisable dans
[`app/auth.py`](app/auth.py), ainsi que les modèles PostgreSQL dans
[`app/models.py`](app/models.py). Le rôle `common` désigne un utilisateur
normal rattaché à une agence.

L'explication du JWT est disponible dans
[`docs/auth_module.md`](../docs/auth_module.md).
Le guide des modèles et contraintes est disponible dans
[`docs/database_models.md`](../docs/database_models.md).
La structure des dossiers est décrite dans
[`docs/project_structure.md`](../docs/project_structure.md).
La synthèse des acteurs, flux et choix techniques est disponible dans
[`docs/architecture_synthesis.md`](../docs/architecture_synthesis.md).

Le conteneur expose `GET /health` sur le port `8000`. La documentation
interactive FastAPI est disponible sur `/docs`.

## Authentification

Les mots de passe sont hachés avec Argon2id. Après un login valide, l'API
émet un JWT signé avec une expiration et le place dans le cookie
`access_token`. Le cookie est `HttpOnly`, `SameSite=Lax` et devient `Secure`
quand `APP_ENV=production`. Un utilisateur supprimé logiquement
(`deleted_at` non nul) est refusé à la connexion et à chaque requête protégée.

Routes disponibles :

- `POST /auth/login` avec le JSON
  `{"username": "admin", "password": "mot-de-passe"}` ;
- `POST /auth/logout` pour supprimer le cookie ;
- `GET /auth/me` pour vérifier la session courante.

En développement, deux comptes de démonstration sont créés automatiquement :

- `admin` / `Admin123!` ;
- `personne1` / `Test1234!`, rattaché à l'agence Paris.

Variables d'environnement :

- `JWT_SECRET_KEY` : secret utilisé pour signer le JWT ;
- `JWT_EXPIRE_MINUTES` : durée du JWT, 30 minutes par défaut ;
- `APP_ENV` : mettre `production` pour activer le cookie `Secure`.

`app/main.py` connecte le module JWT au modèle SQLAlchemy `User` avec deux
fonctions de recherche : par nom et par identifiant.

L'interface Backoffice est disponible sur `/`. Après connexion, `/app.html`
vérifie la session avec `/auth/me` et adapte le contenu au rôle.

En dehors de Docker :

```bash
cd backoffice
uvicorn app.main:app --reload
```

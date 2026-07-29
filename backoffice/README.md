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

En développement, les comptes de démonstration suivants sont créés
automatiquement :

- `admin` / `Admin123!` ;
- `camille.martin`, `thomas.bernard`, `lea.dubois`, `hugo.robert`,
  `chloe.richard`, `nathan.petit`, `ines.durand`, `louis.moreau`,
  `emma.simon`, `gabriel.laurent` et `manon.rousseau` / `Common123!`, rattachés
  à leurs agences de démonstration respectives.

La seed ajoute les 39 produits actifs du catalogue dans chaque agence, avec
des quantités variées (rupture, stock faible et stock disponible). L’agence
d’Annecy possède volontairement un assortiment réduit de 7 produits.

Variables d'environnement :

- `JWT_SECRET_KEY` : secret utilisé pour signer le JWT ;
- `JWT_EXPIRE_MINUTES` : durée du JWT, 30 minutes par défaut ;
- `APP_ENV` : mettre `production` pour activer le cookie `Secure`.
- `SEED_DEMO_DATA` : mettre `false` pour désactiver la seed en développement ;
- `PRODUCT_API_URL` : URL de base du catalogue produit externe
  (`http://external-products-api:5000` dans Docker Compose).

`app/main.py` connecte le module JWT au modèle SQLAlchemy `User` avec deux
fonctions de recherche : par nom et par identifiant.

L'interface Backoffice est disponible sur `/`. Après connexion, un admin est
dirigé vers `/users.html` et un utilisateur `common` vers `/stock.html`.
Le rôle `common` peut :

- consulter uniquement le stock de son agence avec `GET /stock/` ;
- consulter avec `GET /products/` l'intégralité du catalogue actif fourni par
  l'API externe, indépendamment des lignes et quantités du stock local ;
- ajouter un produit connu avec `POST /stock/add` ;
- retirer une quantité disponible avec `POST /stock/remove`.

L'administrateur gère les agences par leur nom depuis `/users.html`. Il peut
les créer, les renommer et supprimer uniquement celles qui ne contiennent ni
utilisateur actif ni stock. L'affectation d'un utilisateur se fait avec un
menu déroulant, sans saisir d'identifiant technique.

Les mots de passe créés ou réinitialisés doivent contenir au moins huit
caractères, dont une majuscule, une minuscule, un chiffre et un caractère
spécial. Les listes d'utilisateurs, d'agences, de stock et de produits sont
paginées dans l'interface.

La contrainte `(agence, produit)` garantit une seule ligne de stock. Les ajouts
successifs augmentent cette ligne au lieu de créer des doublons.

Les noms, SKU et prix sont lus depuis Product API et ne sont jamais enregistrés
dans PostgreSQL. Seuls l'identifiant externe et la quantité par agence sont
persistés. Un produit inconnu est refusé et une indisponibilité de Product API
ne modifie jamais le stock.

Le catalogue et le stock ont des responsabilités distinctes : le catalogue
représente toutes les références actives proposées par le fournisseur, tandis
que le stock représente uniquement les produits et quantités gérés dans
l'agence. Supprimer une ligne de stock ne supprime donc jamais sa référence du
catalogue fournisseur.

En dehors de Docker :

```bash
cd backoffice
python -m app.bootstrap
```

Au démarrage, `app.bootstrap` exécute d’abord `alembic upgrade head`, lance
ensuite la seed idempotente en développement, puis démarre FastAPI. Alembic
gère donc seul le schéma tandis que `app.seed` gère uniquement les données de
démonstration ; les lignes existantes ne sont ni supprimées ni réinitialisées.

Pour démarrer sans la seed de démonstration :

```bash
SEED_DEMO_DATA=false python -m app.bootstrap
```

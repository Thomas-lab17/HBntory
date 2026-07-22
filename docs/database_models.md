# Modèles PostgreSQL — guide pas à pas

Cette partie correspond au jalon 2 du README : créer `Branch`, `User` et
`Stock`, leurs relations et les règles de données.

## 1. Fichiers concernés

| Fichier | Rôle |
|---|---|
| `backoffice/app/database.py` | Configure SQLAlchemy et les sessions. |
| `backoffice/app/models.py` | Contient `Branch`, `User`, `Stock` et `UserRole`. |
| `backoffice/app/main.py` | Crée les tables au démarrage et connecte le JWT à `User`. |
| `backoffice/tests/test_models.py` | Vérifie les relations et contraintes. |

## 2. Modèle `Branch`

Une agence contient :

| Champ | Utilité |
|---|---|
| `id` | Identifiant interne. |
| `name` | Nom unique de l'agence. |
| `created_at` | Date de création. |
| `updated_at` | Date de dernière modification. |

Relations :

- `branch.users` retourne les utilisateurs de l'agence ;
- `branch.stocks` retourne ses lignes de stock.

## 3. Modèle `User`

Un utilisateur contient :

| Champ | Utilité |
|---|---|
| `id` | Identifiant placé dans le JWT. |
| `username` | Identifiant de connexion unique. |
| `password_hash` | Hash Argon2, jamais le mot de passe original. |
| `role` | `admin` ou `common`. |
| `branch_id` | Agence du rôle `common`, facultative pour l'admin. |
| `created_at` | Date de création. |
| `updated_at` | Date de dernière modification. |
| `deleted_at` | Date de suppression logique, `NULL` si le compte est actif. |

La suppression est logique : on remplit `deleted_at` au lieu de supprimer la
ligne. Le module JWT refuse déjà un utilisateur dont `deleted_at` n'est pas
`NULL`.

## 4. Modèle `Stock`

Une ligne de stock contient uniquement :

| Champ | Utilité |
|---|---|
| `id` | Identifiant interne. |
| `branch_id` | Agence concernée. |
| `external_product_id` | Identifiant provenant de Product API. |
| `quantity` | Quantité disponible, jamais négative. |
| `created_at` | Date de création. |
| `updated_at` | Date de dernière modification. |

Aucun nom, prix ou détail produit n'est enregistré localement. Ces
informations restent dans Product API.

## 5. Contraintes métier

### Une ligne par produit et par agence

La contrainte suivante empêche deux lignes identiques dans une même agence :

```text
UNIQUE(branch_id, external_product_id)
```

Le même produit peut toutefois exister dans plusieurs agences.

### Stock non négatif

```text
CHECK(quantity >= 0)
```

PostgreSQL refuse donc une quantité négative, même si une future route API
oublie de la vérifier.

### Clés étrangères

```text
User.branch_id  -> Branch.id
Stock.branch_id -> Branch.id
```

Si une agence est supprimée, ses stocks sont supprimés. Les utilisateurs ne
sont pas supprimés : leur `branch_id` devient `NULL`.

## 6. Création automatique des tables

Au démarrage, `app/main.py` exécute :

```python
Base.metadata.create_all(bind=engine)
```

Cette solution reste simple pour le projet étudiant. Si le schéma évolue plus
tard sans outil de migration, il faudra recréer la base de développement.

### Données de démonstration

En développement, le démarrage ajoute une seule fois :

- les agences Paris et Lyon ;
- `admin` avec le rôle `admin` ;
- `personne1` avec le rôle `common` et l'agence Paris ;
- le produit externe `123` avec une quantité de 10 à Paris.

Les mots de passe viennent de `DEMO_ADMIN_PASSWORD` et
`DEMO_COMMON_PASSWORD`. Aucune donnée de démonstration n'est créée lorsque
`APP_ENV=production`.

## 7. Lancer PostgreSQL et le Backoffice

Depuis la racine :

```bash
docker compose up -d --build postgres backoffice
```

Vérifier l'API :

```bash
curl http://localhost:8000/health
```

Résultat attendu :

```json
{"status":"ok","service":"backoffice"}
```

## 8. Observer les tables

```bash
docker compose exec postgres \
  psql -U hbntory -d hbntory -c "\dt"
```

Les tables attendues sont :

```text
branches
users
stocks
```

Afficher les contraintes de stock :

```bash
docker compose exec postgres \
  psql -U hbntory -d hbntory -c "\d stocks"
```

## 9. Lancer les tests

```bash
cd backoffice
pytest -q
```

Les tests couvrent :

- les relations agence/utilisateur/stock ;
- l'unicité agence/produit ;
- le même produit dans deux agences ;
- le refus d'une quantité négative ;
- les timestamps et le soft-delete ;
- l'absence de détails produit locaux.

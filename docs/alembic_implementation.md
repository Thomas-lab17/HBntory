# Documentation complète sur Alembic

## Sommaire

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Initialisation d'un projet](#initialisation-dun-projet)
4. [Structure des fichiers générés](#structure-des-fichiers-générés)
5. [Configuration](#configuration)
6. [Créer une migration](#créer-une-migration)
7. [Autogenerate](#autogenerate)
8. [Appliquer et annuler des migrations](#appliquer-et-annuler-des-migrations)
9. [Commandes courantes](#commandes-courantes)
10. [Écrire des migrations manuelles](#écrire-des-migrations-manuelles)
11. [Branches et fusions](#branches-et-fusions)
12. [Migrations hors ligne (offline)](#migrations-hors-ligne-offline)
13. [Utilisation avec plusieurs bases de données](#utilisation-avec-plusieurs-bases-de-données)
14. [Intégration avec un framework (Flask/FastAPI)](#intégration-avec-un-framework)
15. [Bonnes pratiques](#bonnes-pratiques)
16. [Dépannage courant](#dépannage-courant)
17. [Ressources](#ressources)

---

## Introduction

Alembic est un outil de **migration de schéma de base de données** pour Python, développé par l'auteur de SQLAlchemy. Il permet de versionner les changements apportés à la structure d'une base de données (création/suppression de tables, ajout/suppression de colonnes, contraintes, index, etc.) de la même façon que Git versionne le code source.

Chaque migration est un script Python indépendant contenant :
- une fonction `upgrade()` qui applique le changement ;
- une fonction `downgrade()` qui annule ce changement.

Ces scripts sont chaînés entre eux via un identifiant de révision et un pointeur vers la révision précédente, formant un historique linéaire (ou ramifié) des évolutions du schéma.

**Cas d'usage typiques :**
- Faire évoluer le schéma d'une base en production sans perte de données.
- Synchroniser le schéma entre plusieurs environnements (dev, staging, prod).
- Travailler en équipe sur un même schéma sans conflits destructeurs.
- Générer automatiquement les migrations à partir des modèles SQLAlchemy.

---

## Installation

Alembic nécessite Python 3.8+ et s'installe via pip :

```bash
pip install alembic
```

Il est généralement utilisé avec SQLAlchemy et un driver de base de données adapté (ex : `psycopg2` pour PostgreSQL, `pymysql` pour MySQL, `sqlite3` intégré à Python) :

```bash
pip install sqlalchemy psycopg2-binary
```

---

## Initialisation d'un projet

Depuis la racine de votre projet :

```bash
alembic init alembic
```

Cette commande crée un répertoire `alembic/` contenant l'infrastructure nécessaire, ainsi qu'un fichier `alembic.ini` à la racine.

Il existe aussi un template asynchrone (utile avec `asyncpg` ou SQLAlchemy en mode async) :

```bash
alembic init -t async alembic
```

---

## Structure des fichiers générés

```
mon_projet/
├── alembic.ini
└── alembic/
    ├── env.py
    ├── README
    ├── script.py.mako
    └── versions/
        └── (les fichiers de migration apparaîtront ici)
```

- **`alembic.ini`** : fichier de configuration principal (URL de connexion, logging, chemins).
- **`env.py`** : script exécuté à chaque commande Alembic ; c'est ici qu'on connecte Alembic aux modèles SQLAlchemy (`target_metadata`) et à la config de connexion.
- **`script.py.mako`** : template utilisé pour générer chaque nouveau fichier de migration.
- **`versions/`** : contient tous les fichiers de migration générés au fil du temps.

---

## Configuration

### `alembic.ini`

L'URL de connexion à la base peut être définie directement :

```ini
sqlalchemy.url = postgresql+psycopg2://user:password@localhost:5432/ma_base
```

En pratique, il est préférable de **ne pas coder l'URL en dur** et de la charger depuis une variable d'environnement dans `env.py` (voir ci-dessous), pour éviter d'exposer des identifiants dans un fichier versionné.

### `env.py`

Deux étapes essentielles à adapter :

**1. Charger l'URL depuis une variable d'environnement :**

```python
import os
from alembic import context

config = context.config
config.set_main_option(
    "sqlalchemy.url",
    os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
)
```

**2. Lier les métadonnées des modèles pour l'autogenerate :**

```python
from myapp.models import Base  # Base = declarative_base() de vos modèles

target_metadata = Base.metadata
```

Sans cette liaison, la commande `--autogenerate` ne pourra pas détecter les différences entre vos modèles Python et la base réelle.

---

## Créer une migration

Pour créer un fichier de migration vide :

```bash
alembic revision -m "creation_table_utilisateurs"
```

Cela génère un fichier dans `versions/`, avec un identifiant unique (hash) et un squelette :

```python
"""creation_table_utilisateurs

Revision ID: 3a1f9c2b7e4d
Revises: 
Create Date: 2026-07-21 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "3a1f9c2b7e4d"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
```

- `revision` : identifiant unique de cette migration.
- `down_revision` : identifiant de la migration précédente (None si c'est la première).

---

## Autogenerate

Alembic peut comparer l'état des modèles SQLAlchemy avec l'état réel de la base et générer automatiquement le script de migration correspondant :

```bash
alembic revision --autogenerate -m "ajout_colonne_email"
```

**Ce qu'Alembic détecte bien :**
- Ajout/suppression de tables.
- Ajout/suppression de colonnes.
- Changement de type de colonne (partiellement, selon le dialecte).
- Ajout/suppression d'index et de contraintes uniques (selon configuration).

**Ce qu'Alembic ne détecte pas nativement (nécessite `compare_type=True` ou plugins) :**
- Renommage de table ou de colonne (interprété comme suppression + création).
- Certains changements de contraintes CHECK.
- Changements purement liés aux données.

⚠️ **Il est impératif de relire chaque migration générée automatiquement** avant de l'appliquer : l'autogenerate peut se tromper, notamment sur les renommages, et il vaut mieux corriger le script manuellement plutôt que de perdre des données.

---

## Appliquer et annuler des migrations

| Commande | Effet |
|---|---|
| `alembic upgrade head` | Applique toutes les migrations jusqu'à la dernière |
| `alembic upgrade +1` | Applique la migration suivante uniquement |
| `alembic upgrade <revision_id>` | Monte jusqu'à une révision précise |
| `alembic downgrade -1` | Annule la dernière migration appliquée |
| `alembic downgrade base` | Revient à l'état initial (aucune migration) |
| `alembic downgrade <revision_id>` | Redescend jusqu'à une révision précise |

---

## Commandes courantes

| Commande | Description |
|---|---|
| `alembic current` | Affiche la révision actuellement appliquée à la base |
| `alembic history` | Affiche l'historique complet des migrations |
| `alembic history --verbose` | Historique détaillé |
| `alembic heads` | Affiche la ou les révisions les plus récentes (utile en cas de branches) |
| `alembic show <revision_id>` | Détails d'une migration précise |
| `alembic stamp head` | Marque la base comme étant à jour sans exécuter les scripts (utile après import initial) |
| `alembic check` | Vérifie si le schéma actuel correspond aux modèles (détecte un autogenerate manquant) |

---

## Écrire des migrations manuelles

Exemple d'ajout de colonne avec valeur par défaut, puis retrait du défaut (bonne pratique pour éviter un verrou long sur une grande table) :

```python
def upgrade():
    op.add_column(
        "utilisateurs",
        sa.Column("email", sa.String(255), nullable=False, server_default="")
    )
    op.alter_column("utilisateurs", "email", server_default=None)

def downgrade():
    op.drop_column("utilisateurs", "email")
```

Exemple de création de table avec clé étrangère et index :

```python
def upgrade():
    op.create_table(
        "commandes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("utilisateur_id", sa.Integer, sa.ForeignKey("utilisateurs.id"), nullable=False),
        sa.Column("montant", sa.Numeric(10, 2), nullable=False),
        sa.Column("cree_le", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_commandes_utilisateur_id", "commandes", ["utilisateur_id"])

def downgrade():
    op.drop_index("ix_commandes_utilisateur_id", table_name="commandes")
    op.drop_table("commandes")
```

Principales opérations disponibles via `op` :
- `op.create_table` / `op.drop_table`
- `op.add_column` / `op.drop_column` / `op.alter_column`
- `op.create_index` / `op.drop_index`
- `op.create_foreign_key` / `op.drop_constraint`
- `op.execute()` — pour du SQL brut (migrations de données, procédures stockées, etc.)

---

## Branches et fusions

Lorsque plusieurs développeurs créent des migrations en parallèle sur des branches Git différentes, deux migrations peuvent pointer vers la même `down_revision`, créant une **branche** dans l'historique Alembic.

Détecter les branches :

```bash
alembic heads
```

Si plusieurs "heads" apparaissent, il faut les fusionner :

```bash
alembic merge -m "fusion_migrations" <revision_1> <revision_2>
```

Cela crée une migration vide dont le `down_revision` référence les deux branches, réunifiant l'historique.

---

## Migrations hors ligne (offline)

Alembic peut générer le SQL correspondant à une migration sans se connecter réellement à la base, utile pour transmettre un script SQL à un DBA :

```bash
alembic upgrade head --sql > migration.sql
```

Cela nécessite que `env.py` implémente correctement le mode `run_migrations_offline()` (présent par défaut dans le template généré par `alembic init`).

---

## Utilisation avec plusieurs bases de données

Alembic supporte les configurations multi-bases via des sections dans `alembic.ini` (`[alembic]`, puis sections nommées) combinées à plusieurs dossiers de migrations, ou via le concept de **plusieurs "branches" nommées** (`branch_labels`) pointant vers des bases distinctes dans un même projet. Cette configuration est plus avancée et documentée dans la section "Multiple Bases" de la documentation officielle.

---

## Intégration avec un framework

### Flask (avec Flask-SQLAlchemy)

Le paquet `Flask-Migrate` encapsule Alembic pour Flask :

```bash
pip install flask-migrate
```

```python
from flask_migrate import Migrate
migrate = Migrate(app, db)
```

Les commandes deviennent alors `flask db init`, `flask db migrate`, `flask db upgrade`.

### FastAPI

FastAPI n'impose pas d'ORM ; Alembic s'utilise directement tel quel, généralement avec SQLAlchemy en mode asynchrone (`alembic init -t async alembic`) et un `env.py` adapté pour exécuter les migrations via une boucle asyncio.

---

## Bonnes pratiques

- **Toujours relire les migrations autogénérées** avant de les committer.
- **Une migration = un changement logique** : évitez de mélanger plusieurs changements non liés dans un seul script.
- **Ne jamais modifier une migration déjà appliquée en production** ; créez plutôt une nouvelle migration corrective.
- **Tester `downgrade()`** autant que `upgrade()`, en particulier avant un déploiement critique.
- **Séparer migrations de schéma et migrations de données** lourdes (utiliser `op.execute()` avec précaution, par lots si le volume est important).
- **Versionner le dossier `versions/`** dans Git au même titre que le code.
- **Utiliser `alembic check`** en CI pour détecter un oubli d'autogenerate.
- **Éviter les valeurs par défaut codées en dur** dans l'URL de connexion ; passer par des variables d'environnement.

---

## Dépannage courant

| Problème | Cause probable | Solution |
|---|---|---|
| `Target database is not up to date` | La base n'est pas à la dernière révision | `alembic upgrade head` avant de générer une nouvelle migration |
| Plusieurs "heads" détectées | Migrations créées en parallèle sur des branches différentes | `alembic merge` |
| Autogenerate ne détecte rien | `target_metadata` non configuré dans `env.py` | Vérifier l'import et l'assignation de `Base.metadata` |
| Renommage de colonne interprété comme suppression+ajout | Limitation connue de l'autogenerate | Corriger manuellement avec `op.alter_column(..., new_column_name=...)` |
| Migration bloquée sur une grosse table | Verrou long dû à `NOT NULL` sans défaut | Ajouter la colonne en nullable, remplir les données, puis contraindre en plusieurs étapes |

---

## Ressources

- Documentation officielle : https://alembic.sqlalchemy.org
- Dépôt GitHub : https://github.com/sqlalchemy/alembic
- Documentation SQLAlchemy (nécessaire en complément) : https://docs.sqlalchemy.org

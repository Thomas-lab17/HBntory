"""Données codées en dur pour le backoffice HBntory.

Version de démonstration sans base de données :
tout est stocké dans des listes/dictionnaires Python en mémoire.
Chaque redémarrage du serveur remet donc les données à zéro.

Règles métier rappelées :
  - un utilisateur "common" est rattaché à une seule branche et ne gère
    que le stock de cette branche ;
  - l'utilisateur "admin" ne touche JAMAIS au stock, il gère les comptes ;
  - la base ne stocke aucune donnée produit, uniquement des product_id ;
  - suppression d'utilisateur = "douce" (soft delete) : on bascule
    is_deleted à True, la ligne reste en mémoire.
"""

from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# BRANCHES
# Chaque branche possède un identifiant unique et un nom.
# ---------------------------------------------------------------------------
BRANCHES = [
    {"id": 1, "name": "Paris"},
    {"id": 2, "name": "Lyon"},
]

# ---------------------------------------------------------------------------
# UTILISATEURS
# Mots de passe écrits en clair ici (c'est une démo) puis hachés une seule
# fois au démarrage du module avec scrypt (werkzeug). Ensuite seul le hash
# circule : on ne compare jamais de mot de passe en clair.
#
#   role      : "admin" (gestion des utilisateurs uniquement)
#               ou "common" (gestion du stock de sa branche uniquement)
#   branch_id : branche de rattachement ; None pour l'admin
#   is_deleted: True = compte supprimé (doux), connexion refusée,
#               tokens existants invalidés à chaque requête
# ---------------------------------------------------------------------------
_PLAIN_USERS = [
    # Le super-utilisateur : gère les comptes, jamais le stock.
    {"id": 1, "username": "admin", "password": "admin",
     "role": "admin", "branch_id": None},
    # Utilisateur lambda rattaché à Paris (id 1).
    {"id": 2, "username": "personne1", "password": "common",
     "role": "common", "branch_id": 1},
]

# Hachage des mots de passe au chargement -> USERS est LA liste de référence.
USERS = []
for _u in _PLAIN_USERS:
    _plain = _u.pop("password")
    USERS.append({**_u, "password_hash": generate_password_hash(_plain), "is_deleted": False})
del _u, _plain

# ---------------------------------------------------------------------------
# STOCK
# Une ligne = la quantité d'un produit dans une branche donnée.
# Aucune info produit n'est stockée : juste product_id (fourni par la
# future API produits externe).
# Deux lignes de démo pré-chargées pour Paris afin que l'interface ne soit
# pas vide au premier test.
# ---------------------------------------------------------------------------
STOCKS = [
    {"id": 1, "branch_id": 1, "product_id": 101, "quantity": 10},
    {"id": 2, "branch_id": 1, "product_id": 202, "quantity": 4},
]

# Compteurs pour générer les prochains identifiants (simulent l'AUTOINCREMENT).
_next_user_id = 3
_next_stock_id = 3


def next_user_id():
    """Retourne puis réserve le prochain identifiant utilisateur libre."""
    global _next_user_id
    value = _next_user_id
    _next_user_id += 1
    return value


def next_stock_id():
    """Retourne puis réserve le prochain identifiant de ligne de stock."""
    global _next_stock_id
    value = _next_stock_id
    _next_stock_id += 1
    return value


# ---------------------------------------------------------------------------
# PETITS ACCESSEURS (utilisés par app.py pour ne pas dupliquer les boucles)
# ---------------------------------------------------------------------------

def find_branch(branch_id):
    """Retourne la branche correspondante, ou None si introuvable."""
    return next((b for b in BRANCHES if b["id"] == branch_id), None)


def find_branch_by_name(name):
    """Retourne la branche portant ce nom, ou None."""
    return next((b for b in BRANCHES if b["name"] == name), None)


def find_user(user_id):
    """Retourne l'utilisateur (même supprimé) correspondant, ou None."""
    return next((u for u in USERS if u["id"] == user_id), None)


def find_active_user_by_username(username):
    """Retourne l'utilisateur actif portant ce nom, ou None (connexion)."""
    return next(
        (u for u in USERS if u["username"] == username and not u["is_deleted"]),
        None,
    )


def find_any_user_by_username(username):
    """Comme find_active_user_by_username mais sans filtre is_deleted."""
    return next((u for u in USERS if u["username"] == username), None)


def find_stock(branch_id, product_id):
    """Retourne la ligne de stock (branche, produit), ou None."""
    return next(
        (
            s
            for s in STOCKS
            if s["branch_id"] == branch_id and s["product_id"] == product_id
        ),
        None,
    )


def serialize_user(u):
    """Formate un utilisateur pour les réponses JSON de l'API."""
    branch = find_branch(u["branch_id"])
    return {
        "id": u["id"],
        "username": u["username"],
        "role": u["role"],
        "branch_id": u["branch_id"],
        "branch_name": branch["name"] if branch else None,
        "is_deleted": u["is_deleted"],
    }


def serialize_stock(s):
    """Formate une ligne de stock pour les réponses JSON de l'API."""
    return {
        "id": s["id"],
        "product_id": s["product_id"],
        "quantity": s["quantity"],
    }

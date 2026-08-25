"""Backoffice HBntory — API JSON pure (le frontend est une page statique).

Rôles et droits :
  - admin  : gère uniquement les utilisateurs (/api/users...)
  - common : gère uniquement le stock de SA branche (/api/stock...)

Authentification :
  - jeton JWT « bearer » (PyJWT, HS256, expiration 12 h) obtenu via
    POST /api/login puis envoyé dans l'en-tête "Authorization: Bearer <token>" ;
  - la branche de l'utilisateur est TOUJOURS relue côté serveur depuis le
    token, jamais depuis une donnée envoyée par le client.

Stockage : aucune base de données — les données vivent en mémoire dans
data.py (voir data.py pour le détail des structures).
"""

import datetime as dt
import os
from functools import wraps

import jwt
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

import data

# Durée de vie d'un jeton, en heures.
TOKEN_HOURS = 12



def _static_folder():
    """Chemin du dossier frontend statique.

    Deux layouts coexistent selon la façon de lancer l'application :
      - Docker : /app/app.py + /app/frontend (copies séparées dans l'image) ;
      - local  : backoffice/backend/app.py + backoffice/frontend (dossier
                 voisin du dossier backend, donc « .. » par rapport à ce
                 fichier).
    On retourne le premier candidat qui existe ; si aucun, Flask renverra
    une 404 pour les fichiers statiques.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = (
        os.path.join(here, "frontend"),
        os.path.join(here, "..", "frontend"),
    )
    return next((c for c in candidates if os.path.isdir(c)), candidates[0])


def create_app():
    """Construit l'application Flask (toutes les routes /api/* + page /)."""
    app = Flask(__name__, static_folder=_static_folder(), static_url_path="")
    # Clé secrète utilisée pour signer les JWT (surchargeable par variable
    # d'environnement, cf. docker-compose.yml).
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    # -----------------------------------------------------------------------
    # JETONS JWT
    # -----------------------------------------------------------------------

    def make_token(user):
        """Fabrique un JWT signé identifiant l'utilisateur pour 12 h."""
        now = dt.datetime.now(dt.timezone.utc)
        payload = {
            "sub": str(user["id"]),   # sujet du token = id utilisateur
            "role": user["role"],     # rôle copié pour info (revalidé quand même)
            "iat": now,               # date d'émission
            "exp": now + dt.timedelta(hours=TOKEN_HOURS),
        }
        return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

    def current_user():
        """Relit l'utilisateur porteur du token, ou None si invalide.

        Appelé À CHAQUE requête protégée : un compte supprimé entre-temps
        (is_deleted=True) voit donc son token devenir immédiatement inutilisable.
        """
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        try:
            payload = jwt.decode(
                auth.removeprefix("Bearer "),
                app.config["SECRET_KEY"],
                algorithms=["HS256"],
            )
        except jwt.PyJWTError:
            return None
        # Un utilisateur supprimé ne doit plus jamais être résolu.
        user = data.find_user(int(payload["sub"]))
        if user is None or user["is_deleted"]:
            return None
        return user

    # -----------------------------------------------------------------------
    # DÉCORATEURS DE CONTRÔLE D'ACCÈS
    # Ils s'enchaînent : admin_required/common_required incluent déjà
    # login_required, donc l'identité est vérifiée avant le rôle.
    # -----------------------------------------------------------------------

    def login_required(fn):
        """Exige un token valide ; injecte l'utilisateur dans la vue."""

        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify(error="Authentification requise"), 401
            return fn(user, *args, **kwargs)

        return wrapper

    def admin_required(fn):
        """Réserve la route au rôle admin (gestion des comptes)."""

        @login_required
        @wraps(fn)
        def wrapper(user, *args, **kwargs):
            if user["role"] != "admin":
                return jsonify(error="Accès administrateur requis"), 403
            return fn(user, *args, **kwargs)

        return wrapper

    def common_required(fn):
        """Réserve la route au rôle common avec branche obligatoire."""

        @login_required
        @wraps(fn)
        def wrapper(user, *args, **kwargs):
            if user["role"] != "common":
                return jsonify(error="Seuls les utilisateurs communs gèrent le stock"), 403
            if user["branch_id"] is None:
                return jsonify(error="L'utilisateur n'a pas de branche assignée"), 400
            return fn(user, *args, **kwargs)

        return wrapper

    def parse_positive_int(value, field):
        """Convertit value en entier strictement positif, sinon ValueError."""
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field} doit être un entier")
        if number <= 0:
            raise ValueError(f"{field} doit être un entier positif")
        return number

    # -----------------------------------------------------------------------
    # PAGE D'ACCUEIL : la page unique du frontend (HTML/JS/CSS statiques)
    # -----------------------------------------------------------------------

    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    # -----------------------------------------------------------------------
    # AUTHENTIFICATION
    # -----------------------------------------------------------------------

    @app.route("/api/login", methods=["POST"])
    def login():
        """Connexion : {username, password} -> {token, user}.

        Public. Retourne 400 si champs manquants, 401 si identifiants faux
        ou compte supprimé.
        """
        body = request.get_json(silent=True) or {}
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        if not username or not password:
            return jsonify(error="Nom d'utilisateur et mot de passe requis"), 400
        # find_active_user_by_username exclut déjà les comptes supprimés.
        user = data.find_active_user_by_username(username)
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify(error="Identifiants invalides"), 401
        return jsonify(
            token=make_token(user), token_type="Bearer", user=data.serialize_user(user)
        )

    @app.route("/api/me", methods=["GET"])
    def me():
        """Qui suis-je ? Retourne {user: null} (200) si non connecté."""
        user = current_user()
        if user is None:
            return jsonify(user=None), 200
        return jsonify(user=data.serialize_user(user))

    # -----------------------------------------------------------------------
    # BRANCHES (lecture seule, tout utilisateur connecté)
    # -----------------------------------------------------------------------

    @app.route("/api/branches", methods=["GET"])
    @login_required
    def list_branches(user):
        branches = sorted(data.BRANCHES, key=lambda b: b["name"])
        return jsonify(branches=[{"id": b["id"], "name": b["name"]} for b in branches])

    # -----------------------------------------------------------------------
    # STOCK — réservé aux utilisateurs "common", bornés à LEUR branche
    # (la branche vient du token, jamais du client)
    # -----------------------------------------------------------------------

    @app.route("/api/stock", methods=["GET"])
    @common_required
    def get_stock(user):
        stocks = sorted(
            (s for s in data.STOCKS if s["branch_id"] == user["branch_id"]),
            key=lambda s: s["product_id"],
        )
        branch = data.find_branch(user["branch_id"])
        return jsonify(
            branch=branch["name"],
            stock=[data.serialize_stock(s) for s in stocks],
        )

    @app.route("/api/stock/add", methods=["POST"])
    @common_required
    def add_stock(user):
        """Ajoute des unités au stock de la branche de l'utilisateur.

        Règle : ajouter deux fois le même produit FUSIONNE les quantités
        sur une seule ligne (une ligne par couple branche/produit).
        201 même en fusion ; 400 si entrées invalides.
        """
        body = request.get_json(silent=True) or {}
        try:
            product_id = parse_positive_int(body.get("product_id"), "product_id")
            quantity = parse_positive_int(body.get("quantity"), "quantity")
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

        stock = data.find_stock(user["branch_id"], product_id)
        if stock is None:
            # Première entrée de ce produit dans cette branche : nouvelle ligne.
            stock = {
                "id": data.next_stock_id(),
                "branch_id": user["branch_id"],
                "product_id": product_id,
                "quantity": quantity,
            }
            data.STOCKS.append(stock)
        else:
            # Le produit existe déjà : simple fusion des quantités.
            stock["quantity"] += quantity
        return jsonify(stock=data.serialize_stock(stock)), 201

    @app.route("/api/stock/remove", methods=["POST"])
    @common_required
    def remove_stock(user):
        """Retire des unités du stock de la branche de l'utilisateur.

        Règles : le produit doit exister dans la branche (sinon 404) et le
        stock ne peut JAMAIS passer sous 0 (sinon 400).
        """
        body = request.get_json(silent=True) or {}
        try:
            product_id = parse_positive_int(body.get("product_id"), "product_id")
            quantity = parse_positive_int(body.get("quantity"), "quantity")
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

        stock = data.find_stock(user["branch_id"], product_id)
        if stock is None:
            return jsonify(error=f"Produit {product_id} introuvable en stock"), 404
        if stock["quantity"] - quantity < 0:
            return jsonify(
                error=f"Stock insuffisant : il ne reste que "
                      f"{stock['quantity']} unités du produit {product_id}"
            ), 400
        stock["quantity"] -= quantity
        return jsonify(stock=data.serialize_stock(stock))

    # -----------------------------------------------------------------------
    # UTILISATEURS — réservé à l'admin
    # -----------------------------------------------------------------------

    @app.route("/api/users", methods=["GET"])
    @admin_required
    def list_users(user):
        users = sorted(data.USERS, key=lambda u: u["id"])
        return jsonify(users=[data.serialize_user(u) for u in users])

    @app.route("/api/users", methods=["POST"])
    @admin_required
    def create_user(user):
        """Crée un utilisateur ; le rôle est TOUJOURS forcé à "common".

        L'API ne permet jamais de créer un second admin.
        201 créé · 400 champs manquants ou branche invalide · 409 doublon.
        """
        body = request.get_json(silent=True) or {}
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        if not username or not password:
            return jsonify(error="Nom d'utilisateur et mot de passe requis"), 400
        if data.find_any_user_by_username(username):
            return jsonify(error="Ce nom d'utilisateur existe déjà"), 409
        branch = data.find_branch(body.get("branch_id"))
        if branch is None:
            return jsonify(error="Un branch_id valide est requis"), 400

        new_user = {
            "id": data.next_user_id(),
            "username": username,
            # Hachage scrypt : jamais de mot de passe en clair en mémoire.
            "password_hash": generate_password_hash(password),
            "role": "common",
            "branch_id": branch["id"],
            "is_deleted": False,
        }
        data.USERS.append(new_user)
        return jsonify(user=data.serialize_user(new_user)), 201

    @app.route("/api/users/<int:user_id>", methods=["PATCH"])
    @admin_required
    def update_user(user, user_id):
        """Modifie nom d'utilisateur / mot de passe / branche d'un compte.

        Le compte admin lui-même est protégé : toute tentative -> 400.
        404 cible inexistante · 400 admin protégé ou valeurs invalides ·
        409 nouveau nom déjà pris.
        """
        target = data.find_user(user_id)
        if target is None:
            return jsonify(error="Utilisateur introuvable"), 404
        if target["role"] == "admin":
            return jsonify(error="Le compte admin ne peut pas être modifié"), 400

        body = request.get_json(silent=True) or {}

        if "username" in body:
            username = (body.get("username") or "").strip()
            if not username:
                return jsonify(error="Le nom d'utilisateur ne peut pas être vide"), 400
            taken = data.find_any_user_by_username(username)
            if taken and taken["id"] != target["id"]:
                return jsonify(error="Ce nom d'utilisateur existe déjà"), 409
            target["username"] = username

        if "password" in body:
            if not body.get("password"):
                return jsonify(error="Le mot de passe ne peut pas être vide"), 400
            target["password_hash"] = generate_password_hash(body["password"])

        if "branch_id" in body:
            branch = data.find_branch(body.get("branch_id"))
            if branch is None:
                return jsonify(error="branch_id invalide"), 400
            target["branch_id"] = branch["id"]

        return jsonify(user=data.serialize_user(target))

    @app.route("/api/users/<int:user_id>", methods=["DELETE"])
    @admin_required
    def delete_user(user, user_id):
        """Suppression DOUCE : is_deleted=True, la ligne reste en mémoire.

        Effets : connexion refusée + tous les tokens existants deviennent
        inutilisables (current_user relit la mémoire à chaque requête).
        Le compte admin ne peut jamais être supprimé -> 400.
        """
        target = data.find_user(user_id)
        if target is None:
            return jsonify(error="Utilisateur introuvable"), 404
        if target["role"] == "admin":
            return jsonify(error="Le compte admin ne peut pas être supprimé"), 400
        target["is_deleted"] = True
        return jsonify(user=data.serialize_user(target))

    return app


# Instance globale : `flask run` comme `python app.py` la trouvent ici.
app = create_app()

if __name__ == "__main__":
    # 0.0.0.0 : écoute depuis le conteneur Docker (port publié 5000).
    app.run(host="0.0.0.0", port=5000)

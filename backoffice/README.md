# Backoffice API

Objectif : fournir l'API sécurisée utilisée par le backoffice pour gérer les
utilisateurs, les agences et le stock.

Cette partie contiendra les modèles SQLAlchemy, les migrations Alembic,
l'authentification JWT et les autorisations : l'administrateur gère les comptes,
tandis qu'un utilisateur commun gère exclusivement le stock de son agence.

Le conteneur expose temporairement `GET /health` sur le port `8000`. La
documentation interactive FastAPI sera disponible sur `/docs`.

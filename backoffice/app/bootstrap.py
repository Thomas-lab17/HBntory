"""Prépare la base puis démarre le serveur Backoffice."""

from alembic import command
from alembic.config import Config
import uvicorn

from app.seed import seed_demo_data


def main() -> None:
    """Applique les migrations, complète les données de démo et démarre FastAPI."""
    command.upgrade(Config("alembic.ini"), "head")
    seed_demo_data()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

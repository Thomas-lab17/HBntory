"""Règles communes de validation des mots de passe du Backoffice."""

import re


PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_HELP = (
    "8 caractères minimum, avec une majuscule, une minuscule, "
    "un chiffre et un caractère spécial."
)


def validate_password_strength(password: str) -> str:
    """Valide un mot de passe et retourne sa valeur inchangée."""
    errors = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"au moins {PASSWORD_MIN_LENGTH} caractères")
    if len(password) > PASSWORD_MAX_LENGTH:
        errors.append(f"au maximum {PASSWORD_MAX_LENGTH} caractères")
    if not re.search(r"[a-z]", password):
        errors.append("une minuscule")
    if not re.search(r"[A-Z]", password):
        errors.append("une majuscule")
    if not re.search(r"\d", password):
        errors.append("un chiffre")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("un caractère spécial")

    if errors:
        raise ValueError("Le mot de passe doit contenir " + ", ".join(errors) + ".")
    return password

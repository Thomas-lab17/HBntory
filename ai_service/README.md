# AI Query Service

Répond aux questions publiques à partir des **données réelles** :

- catalogue produit via `product-mcp`
- stock / agences via l’API interne Backoffice (`X-Internal-Api-Key`)

## Endpoints

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `GET` | `/health` | Santé du service |
| `POST` | `/ask` | Question → réponse agent |

### `POST /ask`

```json
{ "question": "Quel est le prix du Holberton Student Laptop 14 ?" }
```

Via le client public : `POST http://localhost:8080/api/ask`

## Variables d’environnement

| Variable | Défaut compose | Rôle |
|----------|----------------|------|
| `PRODUCT_MCP_URL` | `http://product-mcp:8002` | Outils produit |
| `STOCK_API_URL` | `http://backoffice:8000` | Stock / agences |
| `INTERNAL_API_KEY` | (partagé avec backoffice) | Auth API interne |

## Exemples de questions

- `Quel est le prix du Holberton Student Laptop 14 ?`
- `Est-ce que le produit 1 est disponible à Paris ?`
- `Quels sont les horaires de l'agence de Lyon ?` (nom OK ; adresse/horaires non en base)

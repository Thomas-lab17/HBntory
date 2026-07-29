# Product MCP Server

Isole l’accès au catalogue produit externe et expose des outils stables pour l’IA.

## HTTP (conteneur Docker)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `GET` | `/health` | Santé |
| `GET` | `/tools/list_products` | Liste catalogue |
| `GET` | `/tools/products/{id}` | Détail par id ou SKU |

Env : `PRODUCT_API_URL` (ex. `http://external-products-api:5000`).

## MCP stdio (optionnel)

`app/server.py` pour le protocole MCP classique (`list_products`, `get_product`).

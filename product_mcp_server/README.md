# Product MCP Server

Objectif : fournir à l'assistant IA un accès contrôlé à l'API Product externe,
sans mélanger cette intégration avec les données locales de stock.

À l'étape dédiée, ce service proposera les outils MCP `list_products` et
`get_product_details(product_id)`, avec des réponses claires pour les produits inconnus,
les erreurs réseau et les indisponibilités de l'API externe.

Le conteneur expose temporairement `GET /health` sur le port `8002`.

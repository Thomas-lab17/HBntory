# AI Query Service

Objectif : répondre aux questions des visiteurs à partir des stocks réels et
des informations produit récupérées via le serveur MCP.

Le service ne modifie jamais le stock. Il devra couvrir les détails produit, la
disponibilité d'un produit par agence, les produits d'une agence et les listes
de courses, tout en refusant les demandes hors périmètre.

Le conteneur expose temporairement `GET /health` sur le port `8001`.

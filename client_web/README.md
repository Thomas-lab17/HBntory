# Client Web

Page publique (Nginx) pour poser une question sur les produits et les stocks,
sans authentification.

L'interface appelle le service IA via un reverse proxy Nginx :

- UI : `http://localhost:8080`
- Proxy : `POST /api/ask` → `ai-service:8001/ask`

États gérés : chargement, réponse, erreur de service.

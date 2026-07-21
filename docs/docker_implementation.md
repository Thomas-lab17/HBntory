# Documentation de développement

## Docker : rôle des fichiers

| Fichier | Rôle |
|---|---|
| `docker-compose.yml` | Décrit l'environnement local complet : les cinq services, leurs ports, les dépendances et le volume PostgreSQL persistant. |
| `backoffice/Dockerfile` | Construit l'image Python de l'API Backoffice et lance Uvicorn sur le port `8000`. |
| `ai_service/Dockerfile` | Construit l'image Python du service de questions IA et lance Uvicorn sur le port `8001`. |
| `product_mcp_server/Dockerfile` | Construit l'image Python du serveur Product MCP et lance Uvicorn sur le port `8002`. |
| `client_web/Dockerfile` | Construit l'image Nginx qui sert le client public sur le port `80` du conteneur. |
| `.env.example` | Modèle de variables locales. Copier ce fichier vers `.env` et choisir un mot de passe PostgreSQL avant le premier démarrage. |
| `.gitignore` | Empêche notamment l'ajout du fichier `.env`, des environnements Python et des fichiers locaux de l'IDE. |

## Préparer et lancer le projet

Depuis la racine du dépôt :

```bash
cp .env.example .env
# Modifier POSTGRES_PASSWORD dans .env
docker compose up -d --build
```

`--build` reconstruit les images si les `Dockerfile`, les dépendances ou le
code ont changé. `-d` démarre les conteneurs en arrière-plan et rend le terminal
immédiatement disponible.

Les ports par défaut sont :

| Service | Adresse locale |
|---|---|
| Client public | `http://localhost:8080` |
| Backoffice API | `http://localhost:8000/docs` |
| Service IA | `http://localhost:8001/docs` |
| Product MCP | `http://localhost:8002/docs` |

## Commandes Docker Compose utiles

```bash
# Voir l'état des conteneurs du projet
docker compose ps

# Démarrer les services déjà construits
docker compose up -d

# Reconstruire et redémarrer après une modification
docker compose up -d --build

# Arrêter et supprimer les conteneurs et le réseau du projet
docker compose down

# Arrêter et supprimer aussi le volume PostgreSQL : perte des données locales
docker compose down -v

# Redémarrer un seul service après une modification ciblée
docker compose up -d --build backoffice
```

Ne pas utiliser `docker compose down -v` pour un simple arrêt : cette commande
supprime le volume `postgres_data` et les données de développement qu'il
contient.

## Consulter les logs et diagnostiquer un problème

```bash
# Suivre les logs de tous les services (Ctrl+C pour quitter l'affichage)
docker compose logs -f

# Suivre uniquement les logs d'un service
docker compose logs -f backoffice
docker compose logs -f ai-service
docker compose logs -f product-mcp

# Afficher les 100 dernières lignes sans suivre les nouveaux messages
docker compose logs --tail=100 postgres

# Vérifier l'état et le code de sortie des conteneurs
docker compose ps
```

Un conteneur dont l'état est `Exited` doit être diagnostiqué avec
`docker compose logs <nom-du-service>`. PostgreSQL doit devenir `healthy` avant
le démarrage du Backoffice. Si un port est déjà pris, modifier la variable
correspondante dans `.env` (par exemple `BACKOFFICE_PORT=9000`) puis relancer
`docker compose up -d`.

## Tester les services Docker

Après `docker compose up -d --build`, vérifier les points de santé :

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

Chaque commande doit répondre avec un JSON contenant `"status":"ok"`. Ouvrir
ensuite `http://localhost:8080` dans un navigateur pour vérifier que le client
public est servi. Les routes FastAPI peuvent aussi être testées depuis les pages
`/docs` indiquées plus haut.

## Vérification avec Docker Desktop

1. Ouvrir Docker Desktop puis lancer `docker compose up -d --build`.
2. Dans **Containers**, ouvrir le projet `hbntory` : les conteneurs
   `postgres`, `backoffice`, `ai-service`, `product-mcp` et `client-web`
   doivent apparaître en cours d'exécution.
3. Sélectionner un conteneur pour consulter l'onglet **Logs**. Les services
   FastAPI doivent indiquer qu'Uvicorn écoute sur `0.0.0.0`; PostgreSQL doit
   indiquer qu'il est prêt à accepter les connexions.
4. Utiliser l'onglet **Inspect** ou **Exec** seulement pour diagnostiquer : la
   validation normale se fait via les URL et les commandes `curl` ci-dessus.
5. À l'arrêt, les conteneurs peuvent disparaître de la vue après
   `docker compose down`, mais le volume `hbntory_postgres_data` reste présent.
   Il est supprimé uniquement avec `docker compose down -v`.

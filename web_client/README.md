# HBntory — Client Web

Interface web publique du projet HBntory : une page où des visiteurs
**anonymes** posent des questions en langage naturel sur les produits et le
stock. Pas de connexion, pas d'historique : chaque question est indépendante.

## État actuel

**Interface seule, sans backend.** La page est entièrement statique et ne
fait aucun appel réseau. Envoyer une question affiche la question dans la
conversation puis une réponse d'attente locale indiquant que le service de
réponses n'est pas encore connecté.

Aucune dépendance, aucun build : HTML + CSS + JavaScript vanilla.

## Fichiers

| Fichier | Rôle |
|---|---|
| `index.html` | Structure de la page : en-tête, fil de discussion (`#messages`), formulaire de question (`#question-form`). |
| `style.css` | Style minimal (bulles utilisateur / assistant, bandeau d'erreur). |
| `app.js` | Comportement : soumission du formulaire, ajout des bulles, message d'attente. Point d'intégration futur marqué en commentaire. |

Ou via Docker Compose (depuis la racine du projet) :

```bash
docker compose up -d web_client
# puis ouvrir http://localhost:8080
```

Le service `web_client` sert les fichiers statiques avec nginx
(`./web_client` monté en lecture seule dans le conteneur).

## Fonctionnement

1. Le visiteur tape une question et valide (Entrée ou bouton « Envoyer »).
2. `app.js` ajoute la question en bulle utilisateur.
3. Pas de service branché pour l'instant : une bulle d'attente s'affiche.

Chaque question est traitée indépendamment ; rien n'est stocké (ni côté
page ni côté serveur). Recharger la page remet la conversation à zéro.

## Endpoints

**Aucun pour l'instant.** La page n'appelle aucun endpoint et ne reçoit
aucune donnée externe.

## Intégration future (prévue, non implémentée)

- Le client enverra chaque question en une requête **POST** au futur
  service de réponses IA (service indépendant du Backoffice) et affichera
  la réponse reçue. Le point d'appel est marqué dans `app.js`.
- D'après le cahier des charges du projet, ce service répondra grâce à un
  agent IA s'appuyant sur :
  - les données produits, via l'**API produits externe** (à travers le
    serveur MCP, `product_mcp_server/`) ;
  - les données de stock, via la **base de données relationnelle**.
- Rien de tout cela n'est branché pour l'instant : ce document décrit
  l'état actuel uniquement.

## Relations

```text
Visiteur anonyme
    │  (navigateur)
    ▼
web_client/  (page statique, sans serveur propre)
    │  ── à venir : POST question ──▶  Service IA (indépendant du Backoffice)
                                        │
                                        ├─▶ produits : API externe via MCP
                                        └─▶ stock : base relationnelle
```

Le client web ne partage aucun code avec le Backoffice et ne le contacte
pas directement.
